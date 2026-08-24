"""OLMoEarth v1.2 Nano vision embedder (torch-native, via olmoearth_pretrain).

Loads a native PyTorch checkpoint (``config.json`` + ``weights.pth``) using the
official ``olmoearth_pretrain`` model loader. The architecture is the full
multi-modal FlexiViT encoder from the OLMoEarth pretraining codebase — not a
reconstruction — so weights load correctly and embeddings are meaningful.

The ``vision_path`` should point to a **directory** containing ``config.json``
and ``weights.pth``. If ``config.json`` is absent, it is downloaded from
HuggingFace (``allenai/OlmoEarth-v1_2-Nano``) on first load.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from geomemory.core.exceptions import ModelNotLoadedError
from geomemory.embeddings.normalization import l2_normalize

# Sentinel-2 L2A has 12 bands — the primary spatial modality used for generic
# multispectral / GeoTIFF inputs. Arbitrary channel counts are padded (or
# truncated) to 12 before embedding.
_TARGET_MODALITY = "sentinel2_l2a"
_TARGET_CHANNELS = 12


class OlmoEarthVisionEmbedder:
    """Torch-native OLMoEarth v1.2 Nano vision embedder.

    Loads a native PyTorch checkpoint via ``olmoearth_pretrain`` and produces
    L2-normalized float32 embeddings in the ``image.olmoearth-nano-v12.v1``
    space. Accepts image inputs (paths, bytes, or PIL images).
    """

    space_id = "image.olmoearth-nano-v12.v1"

    def __init__(self, vision_path: str, *, model_id: str = "olmoearth-nano-v1.2") -> None:
        self.vision_path = Path(vision_path)
        self._model_id = model_id
        self._model: Any | None = None
        self._model_dim: int = 128

    @property
    def model_id(self) -> str:
        return self._model_id

    def _load(self) -> Any:
        if self._model is not None:
            return self._model

        if not self.vision_path.exists():
            raise ModelNotLoadedError(
                f"Vision model path not found: {self.vision_path}",
                hint=str(self.vision_path),
            )

        try:
            import torch
            from olmoearth_pretrain.config import Config  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on extra
            raise ModelNotLoadedError(
                "The 'vision' extra is required for OLMoEarth embeddings. "
                "Install with: pip install 'geomemory[vision]'",
                hint="pip install 'geomemory[vision]'",
            ) from exc

        # Resolve model directory + weights file.
        # Accepts either a directory (config.json + weights.pth) or a direct
        # .pth file path (per the vision-embedding spec).
        if self.vision_path.is_file():
            weights_path = self.vision_path
            model_dir = self.vision_path.parent
        else:
            weights_path = self.vision_path / "weights.pth"
            model_dir = self.vision_path

        if not weights_path.is_file():
            raise ModelNotLoadedError(
                f"Vision model weights not found: {weights_path}",
                hint=str(weights_path),
            )

        config_path = model_dir / "config.json"
        if not config_path.is_file():
            self._download_config(config_path)

        try:
            import json

            with config_path.open() as f:
                config_dict = json.load(f)
            # Patch legacy configs that predate use_linear_patch_embed.
            enc = config_dict.get("model", {}).get("encoder_config", {})
            if isinstance(enc, dict) and "use_linear_patch_embed" not in enc:
                config_dict["model"]["encoder_config"]["use_linear_patch_embed"] = False
            model_config = Config.from_dict(config_dict["model"])
            model = model_config.build()
            state_dict = torch.load(str(weights_path), map_location="cpu")
            model.load_state_dict(state_dict)
        except (RuntimeError, ValueError, OSError) as exc:
            raise ModelNotLoadedError(
                f"Failed to load vision model from {weights_path}: {exc}",
                hint=str(weights_path),
            ) from exc

        self._model = model
        self._model.eval()
        return self._model

    @staticmethod
    def _download_config(config_path: Path) -> None:
        """Download the OLMoEarth-v1_2-Nano config.json from HuggingFace."""
        try:
            from huggingface_hub import hf_hub_download

            downloaded = hf_hub_download("allenai/OlmoEarth-v1_2-Nano", "config.json")
            import shutil

            shutil.copy(downloaded, config_path)
        except Exception as exc:  # noqa: BLE001
            raise ModelNotLoadedError(
                f"config.json missing at {config_path} and could not be "
                f"downloaded from HuggingFace: {exc}",
                hint=str(config_path),
            ) from exc

    def _to_modality_tensor(self, image: Any) -> np.ndarray:
        """Convert one image input to a (H, W, C) float32 array."""
        from PIL import Image

        if isinstance(image, (str, Path)):
            img = Image.open(image).convert("RGB")
        elif isinstance(image, (bytes, bytearray, memoryview)):
            img = Image.open(bytes(image)).convert("RGB")
        elif isinstance(image, Image.Image):
            img = image.convert("RGB")
        elif isinstance(image, np.ndarray):
            arr = image.astype(np.float32)
            if arr.ndim == 2:  # single-channel -> replicate to RGB
                arr = np.stack([arr, arr, arr], axis=-1)
            if arr.max() > 1.0:
                arr = arr / 255.0
            img = Image.fromarray((arr * 255).clip(0, 255).astype(np.uint8))
        else:
            raise TypeError(f"Unsupported image type: {type(image).__name__}")

        # The encoder expects fixed-size tiles (trained on 128x128). Large images
        # would explode the token count, so we resize the longest side to 128.
        max_side = 128
        if max(img.size) > max_side:
            img = img.resize((max_side, max_side))

        arr = np.asarray(img, dtype=np.float32)
        # Normalize to [0, 1] regardless of input scale (8-bit, float GeoTIFF, etc.)
        # via per-image min-max. This keeps the embedding invariant to absolute
        # radiometric scale and focuses on spatial/spectral patterns.
        lo, hi = arr.min(), arr.max()
        arr = (arr - lo) / (hi - lo) if hi - lo > 1e-8 else np.zeros_like(arr)

        return arr

    def embed_images(self, images: Any) -> np.ndarray:
        """Embed a sequence of images, returning an (N, D) L2-normalized array."""
        import torch
        from olmoearth_pretrain.datatypes import (  # type: ignore[import-not-found]
            MaskedOlmoEarthSample,
            MaskValue,
        )
        if not images:
            return np.zeros((0, self._model_dim), dtype=np.float32)

        model = self._load()

        # Convert each image to a padded/truncated (H, W, 12) tensor.
        tensors: list[torch.Tensor] = []
        for image in images:
            arr = self._to_modality_tensor(image)  # (H, W, C)
            h, w, c = arr.shape
            if c < _TARGET_CHANNELS:
                padded = np.zeros((h, w, _TARGET_CHANNELS), dtype=np.float32)
                padded[:, :, :c] = arr
            else:
                padded = arr[:, :, :_TARGET_CHANNELS]
            # (H, W, 12) -> (1, H, W, T=1, 12)
            t = torch.from_numpy(padded).unsqueeze(0).unsqueeze(-2)
            tensors.append(t)

        batch = torch.cat(tensors, dim=0)  # (N, H, W, 1, 12)
        n = batch.shape[0]
        mask = torch.full(
            (n, *batch.shape[1:]), MaskValue.ONLINE_ENCODER.value, dtype=torch.long
        )
        timestamps = torch.zeros((n, 1, 3), dtype=torch.long)

        sample = MaskedOlmoEarthSample(
            timestamps=timestamps,
            sentinel2_l2a=batch,
            sentinel2_l2a_mask=mask,
        )

        with torch.inference_mode():
            out = model.encoder(sample, patch_size=8)

        # project_aggregated holds the pooled embedding
        pa = out["project_aggregated"]
        vectors = pa.detach().cpu().numpy().astype(np.float32)
        return l2_normalize(vectors)

    def embed_texts(self, texts: Any) -> np.ndarray | None:
        """OLMoEarth nano is image-embedding only; returns None."""
        return None
