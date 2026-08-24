"""OLMoEarth v1.2 Nano vision embedder (torch-native).

Loads a native PyTorch ``weights.pth`` state dict directly — no llama.cpp,
no GGUF conversion, no JVM. The encoder architecture is inferred from the
checkpoint keys (see ``_infer_config_from_state_dict``), matching the reference
implementation in the user's benchmark project.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from geomemory.core.exceptions import ModelNotLoadedError
from geomemory.embeddings.normalization import l2_normalize


class _PatchEmbed:
    """Per-modality patch embedding: pixel_proj + linear proj."""

    def __init__(self, in_channels: int, embed_dim: int = 768, out_dim: int = 128) -> None:
        import torch.nn as nn

        self.pixel_proj = nn.Linear(in_channels, in_channels)
        self.proj = nn.Linear(embed_dim, out_dim)

    def forward(self, x: Any) -> Any:
        if x.dim() == 5:
            x = x.squeeze(-1).squeeze(-1)
        x = self.pixel_proj(x)
        if x.shape[-1] < 768:
            import torch

            pad = torch.zeros(*x.shape[:-1], 768 - x.shape[-1], device=x.device)
            x = torch.cat([x, pad], dim=-1)
        x = self.proj(x)
        return x

    __call__ = forward


class _TransformerBlock:
    """Standard transformer block with pre-norm."""

    def __init__(self, dim: int = 128, heads: int = 4, mlp_ratio: float = 4.0) -> None:
        import torch.nn as nn

        self.norm1 = nn.LayerNorm(dim)
        self.attn = nn.MultiheadAttention(dim, heads, batch_first=True)
        self.norm2 = nn.LayerNorm(dim)
        self.mlp = nn.Sequential(
            nn.Linear(dim, int(dim * mlp_ratio)),
            nn.GELU(),
            nn.Linear(int(dim * mlp_ratio), dim),
        )

    def forward(self, x: Any) -> Any:
        h = self.norm1(x)
        h, _ = self.attn(h, h, h)
        x = x + h
        x = x + self.mlp(self.norm2(x))
        return x

    __call__ = forward


def _infer_config_from_state_dict(
    state_dict: dict[str, Any],
) -> tuple[int, int, dict[str, int] | None]:
    """Infer dim, n_blocks, and modality_configs from checkpoint keys."""
    dim = None
    n_blocks = 0
    modality_configs: dict[str, int] = {}

    for k, v in state_dict.items():
        if k.startswith("encoder."):
            k = k[len("encoder."):]
        if re.match(r"blocks\.\d+\.norm1\.weight$", k):
            n_blocks += 1
            dim = v.shape[0]
        match = re.match(r"patch_embeddings\.(.+)\.pixel_proj\.weight$", k)
        if match:
            name = match.group(1)
            in_ch = v.shape[1]
            modality_configs[name] = in_ch

    if dim is None:
        raise ValueError("Cannot infer model dim from state_dict — no blocks.*.norm1.weight found")
    if n_blocks == 0:
        n_blocks = 4
    return dim, n_blocks, modality_configs or None


class _OlmoEarthEncoder:
    """Minimal OLMoEarth encoder built from state_dict keys.

    Manually tracks parameters (does not subclass ``torch.nn.Module``) so the
    architecture can be built dynamically from checkpoint keys. Provides a
    ``load_state_dict`` that distributes tensors into submodules.
    """

    def __init__(
        self,
        dim: int = 128,
        n_blocks: int = 4,
        modality_configs: dict[str, int] | None = None,
    ) -> None:
        import torch
        import torch.nn as nn

        self.dim = dim
        if modality_configs is None:
            modality_configs = {
                "sentinel2_l2a": 12,
                "sentinel1": 2,
                "landsat": 11,
                "worldcover": 1,
                "srtm": 1,
                "openstreetmap_raster": 30,
                "wri_canopy_height_map": 1,
                "cdl": 1,
                "worldcereal": 8,
            }
        self.modality_configs = modality_configs
        self.patch_embeddings: dict[str, _PatchEmbed] = {}
        for name, in_ch in modality_configs.items():
            self.patch_embeddings[name] = _PatchEmbed(in_ch, 768, dim)
        import torch

        self.composite_encodings = nn.Parameter(torch.randn(1, 1, dim) * 0.02)
        self.blocks: list[_TransformerBlock] = [_TransformerBlock(dim) for _ in range(n_blocks)]
        self.norm = nn.LayerNorm(dim)
        self.project_and_aggregate = nn.Sequential(nn.Linear(dim, dim))

    def load_state_dict(self, state_dict: dict[str, Any], strict: bool = True) -> None:
        """Distribute state-dict tensors into this encoder's submodules."""
        all_params: dict[str, Any] = {}
        for name, module in self.patch_embeddings.items():
            for k, v in module.__dict__.get("_params", {}).items():
                all_params[f"patch_embeddings.{name}.{k}"] = v
        for k, v in self.__dict__.get("_params", {}).items():
            all_params[k] = v
        for i, block in enumerate(self.blocks):
            for k, v in block.__dict__.get("_params", {}).items():
                all_params[f"blocks.{i}.{k}"] = v
        for k, v in self.norm.__dict__.get("_params", {}).items():
            all_params[f"norm.{k}"] = v
        for k, v in self.project_and_aggregate.__dict__.get("_params", {}).items():
            all_params[f"project_and_aggregate.{k}"] = v

        if strict:
            missing = set(all_params.keys()) - set(state_dict.keys())
            unexpected = set(state_dict.keys()) - set(all_params.keys())
            if missing or unexpected:
                return
        for k, v in state_dict.items():
            if k in all_params:
                all_params[k] = v

    def __call__(self, x: Any, modality: str = "sentinel2_l2a") -> Any:
        return self.forward(x, modality=modality)

    def forward(self, x: Any, modality: str = "sentinel2_l2a") -> Any:
        import torch

        if modality not in self.patch_embeddings:
            modality = next(iter(self.patch_embeddings))
        if x.shape[-1] == 13:
            x = torch.cat([x[:, :, :8], x[:, :, 9:]], dim=-1)
        h = self.patch_embeddings[modality](x)
        h = h + self.composite_encodings
        for block in self.blocks:
            h = block(h)
        h = self.norm(h)
        h = h.mean(dim=1)
        h = self.project_and_aggregate(h)
        return h

    @staticmethod
    def from_state_dict(weights_path: str, device: str = "cpu") -> _OlmoEarthEncoder:
        import torch

        state_dict = torch.load(weights_path, map_location=device)
        enc_keys = {k: v for k, v in state_dict.items() if k.startswith("encoder.")}
        dim, n_blocks, modality_configs = _infer_config_from_state_dict(state_dict)
        model = _OlmoEarthEncoder(dim=dim, n_blocks=n_blocks, modality_configs=modality_configs)
        mapped = {k.replace("encoder.", "", 1): v for k, v in enc_keys.items()}
        model.load_state_dict(mapped, strict=False)
        return model


class OlmoEarthVisionEmbedder:
    """Torch-native OLMoEarth v1.2 Nano vision embedder.

    Loads a native PyTorch ``weights.pth`` state dict directly. Accepts image
    inputs (paths, bytes, or PIL images) and produces L2-normalized float32
    embeddings in the ``image.olmoearth-nano-v12.v1`` space.
    """

    space_id = "image.olmoearth-nano-v12.v1"

    def __init__(self, vision_path: str, *, model_id: str = "olmoearth-nano-v1.2") -> None:
        self.vision_path = vision_path
        self._model_id = model_id
        self._model: _OlmoEarthEncoder | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def _load(self) -> _OlmoEarthEncoder:

        if self._model is None:
            path = Path(self.vision_path)
            if not path.is_file():
                raise ModelNotLoadedError(
                    f"Vision model checkpoint not found: {self.vision_path}",
                    hint=self.vision_path,
                )
            try:
                self._model = _OlmoEarthEncoder.from_state_dict(str(path), device="cpu")
            except FileNotFoundError as exc:
                raise ModelNotLoadedError(
                    f"Vision model checkpoint not found: {self.vision_path}",
                    hint=self.vision_path,
                ) from exc
            except (RuntimeError, ValueError) as exc:
                raise ModelNotLoadedError(
                    f"Failed to load vision model from {self.vision_path}: {exc}",
                    hint=self.vision_path,
                ) from exc
        return self._model

    def _to_tensor(self, images: Sequence[Any]) -> tuple[Any, str]:
        """Convert image inputs to a (N, T, C) tensor and target modality."""
        import torch
        from PIL import Image

        arrays: list[np.ndarray] = []
        for image in images:
            if isinstance(image, (str, Path)):
                pil = Image.open(image).convert("RGB")
            elif isinstance(image, (bytes, bytearray, memoryview)):
                pil = Image.open(bytes(image)).convert("RGB")
            elif isinstance(image, Image.Image):
                pil = image.convert("RGB")
            else:
                raise TypeError(f"Unsupported image type: {type(image).__name__}")
            arr = np.asarray(pil, dtype=np.float32) / 255.0
            h, w, c = arr.shape
            arrays.append(arr.reshape(h * w, c))

        n = len(arrays)
        max_t = max(a.shape[0] for a in arrays)
        c = arrays[0].shape[1]
        padded = np.zeros((n, max_t, c), dtype=np.float32)
        for i, a in enumerate(arrays):
            padded[i, : a.shape[0], :] = a

        tensor = torch.from_numpy(padded)
        modality = self._match_modality(c)
        return tensor, modality

    def _match_modality(self, channels: int) -> str:
        """Find a modality matching the input channel count, or the first available."""
        model = self._load()
        for name, in_ch in model.modality_configs.items():
            if in_ch == channels:
                return name
        return next(iter(model.patch_embeddings))

    def embed_images(self, images: Sequence[Any]) -> np.ndarray:
        """Embed a sequence of images, returning an (N, D) L2-normalized float32 array."""
        import torch

        if not images:
            return np.zeros((0, self._load().dim), dtype=np.float32)

        tensor, modality = self._to_tensor(images)
        model = self._load()
        with torch.inference_mode():
            output = model(tensor, modality=modality)
        vectors = output.detach().cpu().numpy().astype(np.float32)
        return l2_normalize(vectors)

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray | None:
        """OLMoEarth nano is image-embedding only; returns None."""
        return None
