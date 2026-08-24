"""Tests for the OLMoEarth v1.2 Nano torch-native vision embedder."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest


def _make_fake_torch(state_dict: dict[str, np.ndarray] | None = None) -> ModuleType:
    """Build a minimal fake torch module for testing without real torch."""
    torch = ModuleType("torch")
    torch.__path__ = []  # type: ignore[attr-defined]
    torch.nn = ModuleType("torch.nn")
    torch.nn.__path__ = []  # type: ignore[attr-defined]

    class FakeTensor:
        def __init__(self, data: np.ndarray) -> None:
            self._data = data
            self.shape = data.shape
            self.dtype = data.dtype
            self.device = "cpu"

        def dim(self) -> int:
            return self._data.ndim

        def squeeze(self, *args: int) -> FakeTensor:
            return FakeTensor(self._data.squeeze(*args))

        def cat(self, others: list, dim: int = 0) -> FakeTensor:
            all_data = [self._data] + [o._data for o in others]
            return FakeTensor(np.concatenate(all_data, axis=dim))

        def to(self, device: str) -> FakeTensor:
            return self

        def numpy(self) -> np.ndarray:
            return self._data

        def detach(self) -> FakeTensor:
            return self

        def cpu(self) -> FakeTensor:
            return self

        def __getitem__(self, key: object) -> FakeTensor:
            return FakeTensor(self._data[key])

        def __add__(self, other: object) -> FakeTensor:
            other_data = other._data if hasattr(other, "_data") else other
            result = self._data + other_data
            return FakeTensor(result)

        def __truediv__(self, other: object) -> FakeTensor:
            if isinstance(other, FakeTensor):
                return FakeTensor(self._data / other._data)
            return FakeTensor(self._data / other)

        def __rtruediv__(self, other: object) -> FakeTensor:
            return FakeTensor(other / self._data)

        def __mul__(self, other: object) -> FakeTensor:
            return FakeTensor(self._data * other)

        def mean(self, dim: int = 0, keepdims: bool = False) -> FakeTensor:
            return FakeTensor(self._data.mean(axis=dim, keepdims=keepdims))

    class FakeModule:
        def __init__(self) -> None:
            self._params: dict[str, FakeTensor] = {}
            self._modules: dict[str, FakeModule] = {}
            self.training = False

        def __setattr__(self, name: str, value: object) -> None:
            if isinstance(value, FakeTensor):
                self.__dict__.setdefault("_params", {})[name] = value
            elif isinstance(value, FakeModule):
                self.__dict__.setdefault("_modules", {})[name] = value
            else:
                object.__setattr__(self, name, value)

        def __getattr__(self, name: str) -> object:
            if name in self.__dict__.get("_params", {}):
                return self.__dict__["_params"][name]
            if name in self.__dict__.get("_modules", {}):
                return self.__dict__["_modules"][name]
            raise AttributeError(name)

        def parameters(self) -> list[FakeTensor]:
            return list(self.__dict__.get("_params", {}).values())

        def named_parameters(self) -> list[tuple[str, FakeTensor]]:
            return list(self.__dict__.get("_params", {}).items())

        def modules(self) -> list[FakeModule]:
            result: list[FakeModule] = [self]
            for mod in self.__dict__.get("_modules", {}).values():
                result.extend(mod.modules())
            return result

        def eval(self) -> FakeModule:
            return self

        def to(self, device: str) -> FakeModule:
            return self

        def state_dict(self) -> dict[str, FakeTensor]:
            return dict(self.__dict__.get("_params", {}))

        def load_state_dict(self, state_dict: dict[str, object], strict: bool = True) -> object:
            missing: list[str] = []
            unexpected: list[str] = []
            my_keys = set(self.__dict__.get("_params", {}).keys())
            new_keys = set(state_dict.keys())
            if strict:
                missing = list(my_keys - new_keys)
                unexpected = list(new_keys - my_keys)
                if missing or unexpected:
                    return object()
            for k, v in state_dict.items():
                if k in my_keys:
                    self.__dict__["_params"][k] = v
            return object()

    class FakeLinear(FakeModule):
        def __init__(self, in_features: int, out_features: int) -> None:
            super().__init__()
            self.in_features = in_features
            self.out_features = out_features
            self.weight = FakeTensor(np.random.randn(out_features, in_features).astype(np.float32))
            self.bias = FakeTensor(np.zeros(out_features, dtype=np.float32))

        def __call__(self, x: FakeTensor) -> FakeTensor:
            return FakeTensor(x._data @ self.weight._data.T + self.bias._data)

    class FakeLayerNorm(FakeModule):
        def __init__(self, normalized_shape: int) -> None:
            super().__init__()
            self.weight = FakeTensor(np.ones(normalized_shape, dtype=np.float32))
            self.bias = FakeTensor(np.zeros(normalized_shape, dtype=np.float32))

        def __call__(self, x: FakeTensor) -> FakeTensor:
            mean = x._data.mean(axis=-1, keepdims=True)
            std = x._data.std(axis=-1, keepdims=True) + 1e-5
            return FakeTensor(((x._data - mean) / std) * self.weight._data + self.bias._data)

    class FakeMultiheadAttention(FakeModule):
        def __init__(self, embed_dim: int, num_heads: int, **kwargs: object) -> None:
            super().__init__()
            self.embed_dim = embed_dim
            self.num_heads = num_heads

        def __call__(
            self, q: FakeTensor, k: FakeTensor, v: FakeTensor
        ) -> tuple[FakeTensor, FakeTensor]:
            return q, FakeTensor(
                np.zeros((q._data.shape[0], q._data.shape[1], 1), dtype=np.float32)
            )

    class FakeGELU(FakeModule):
        def __call__(self, x: FakeTensor) -> FakeTensor:
            return x

    class FakeSequential(FakeModule):
        def __init__(self, *layers: FakeModule) -> None:
            super().__init__()
            self.layers = list(layers)

        def __call__(self, x: FakeTensor) -> FakeTensor:
            for layer in self.layers:
                x = layer(x)
            return x

    class FakeModuleList(FakeModule):
        def __init__(self, modules: list[FakeModule]) -> None:
            super().__init__()
            self._module_list = modules

        def __iter__(self) -> object:
            return iter(self._module_list)

        def __call__(self, x: FakeTensor) -> FakeTensor:
            for m in self._module_list:
                x = m(x)
            return x

    class FakeModuleDict(FakeModule):
        def __init__(self, modules: dict[str, FakeModule] | None = None) -> None:
            super().__init__()
            self._module_dict: dict[str, FakeModule] = modules if modules is not None else {}

        def __setitem__(self, key: str, value: FakeModule) -> None:
            self._module_dict[key] = value

        def __getitem__(self, key: str) -> FakeModule:
            return self._module_dict[key]

        def __contains__(self, key: str) -> bool:
            return key in self._module_dict

        def __iter__(self) -> object:
            return iter(self._module_dict)

        def items(self) -> list[tuple[str, FakeModule]]:
            return list(self._module_dict.items())

        def keys(self) -> list[str]:
            return list(self._module_dict.keys())

    class FakeParameter(FakeTensor):
        def __init__(self, data: np.ndarray | FakeTensor) -> None:
            if isinstance(data, FakeTensor):
                super().__init__(data._data)
            else:
                super().__init__(data)

    class FakeInferenceMode:
        def __enter__(self) -> FakeInferenceMode:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    def fake_load(path: str, map_location: str = "cpu") -> dict[str, FakeTensor]:
        if state_dict is not None:
            return {
                k: FakeTensor(v) if not isinstance(v, FakeTensor) else v
                for k, v in state_dict.items()
            }
        # Try to load from the actual file (written by _make_state_dict via pickle)
        import pickle
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            return {
                k: FakeTensor(v) if not isinstance(v, FakeTensor) else v
                for k, v in data.items()
            }
        except Exception as exc:
            raise RuntimeError(f"Failed to load checkpoint from {path}: {exc}") from exc

    def fake_from_numpy(array: np.ndarray, dtype: object = None) -> FakeTensor:
        return FakeTensor(array.astype(np.float32))

    def fake_tensor(data: np.ndarray, dtype: object = None, device: str = "cpu") -> FakeTensor:
        return FakeTensor(np.asarray(data, dtype=np.float32))

    torch.Tensor = FakeTensor  # type: ignore[attr-defined]
    torch.nn.Module = FakeModule  # type: ignore[attr-defined]
    torch.nn.Linear = FakeLinear  # type: ignore[attr-defined]
    torch.nn.LayerNorm = FakeLayerNorm  # type: ignore[attr-defined]
    torch.nn.MultiheadAttention = FakeMultiheadAttention  # type: ignore[attr-defined]
    torch.nn.GELU = FakeGELU  # type: ignore[attr-defined]
    torch.nn.Sequential = FakeSequential  # type: ignore[attr-defined]
    torch.nn.ModuleList = FakeModuleList  # type: ignore[attr-defined]
    torch.nn.ModuleDict = FakeModuleDict  # type: ignore[attr-defined]
    torch.nn.Parameter = FakeParameter  # type: ignore[attr-defined]
    torch.load = fake_load  # type: ignore[attr-defined]
    torch.from_numpy = fake_from_numpy  # type: ignore[attr-defined]
    torch.tensor = fake_tensor  # type: ignore[attr-defined]
    torch.inference_mode = FakeInferenceMode  # type: ignore[attr-defined]
    def fake_zeros(*args: object, **kwargs: object) -> FakeTensor:
        # Filter out non-shape args like device=...
        shape_args = [a for a in args if isinstance(a, (int, tuple, list))]
        if len(shape_args) == 1 and isinstance(shape_args[0], (tuple, list)):
            return FakeTensor(np.zeros(shape_args[0], dtype=np.float32))
        return FakeTensor(np.zeros(tuple(shape_args), dtype=np.float32))

    torch.zeros = fake_zeros  # type: ignore[attr-defined]
    torch.randn = (
        lambda *args, **kwargs: FakeTensor(np.random.randn(*args).astype(np.float32))
    )  # type: ignore[attr-defined]
    torch.cat = (
        lambda tensors, dim=0: FakeTensor(
            np.concatenate([t._data for t in tensors], axis=dim)
        )
    )  # type: ignore[attr-defined]
    torch.save = lambda obj, path: None  # type: ignore[attr-defined]
    torch.device = lambda x: x  # type: ignore[attr-defined]
    torch.float32 = np.float32  # type: ignore[attr-defined]
    torch.no_grad = FakeInferenceMode  # type: ignore[attr-defined]

    return torch


def _make_state_dict(
    dim: int = 128, n_blocks: int = 4, in_channels: int = 3
) -> dict[str, np.ndarray]:
    """Build a minimal valid state dict matching the expected key pattern."""
    state_dict: dict[str, np.ndarray] = {}
    state_dict["encoder.patch_embeddings.rgb.pixel_proj.weight"] = np.random.randn(
        in_channels, in_channels
    ).astype(np.float32)
    state_dict["encoder.patch_embeddings.rgb.proj.weight"] = np.random.randn(
        dim, 768
    ).astype(np.float32)
    state_dict["encoder.composite_encodings"] = (
        np.random.randn(1, 1, dim).astype(np.float32) * 0.02
    )
    for i in range(n_blocks):
        state_dict[f"encoder.blocks.{i}.norm1.weight"] = np.ones(dim, dtype=np.float32)
        state_dict[f"encoder.blocks.{i}.norm1.bias"] = np.zeros(dim, dtype=np.float32)
        state_dict[f"encoder.blocks.{i}.norm2.weight"] = np.ones(dim, dtype=np.float32)
        state_dict[f"encoder.blocks.{i}.norm2.bias"] = np.zeros(dim, dtype=np.float32)
    state_dict["encoder.norm.weight"] = np.ones(dim, dtype=np.float32)
    state_dict["encoder.norm.bias"] = np.zeros(dim, dtype=np.float32)
    state_dict["encoder.project_and_aggregate.0.weight"] = np.random.randn(
        dim, dim
    ).astype(np.float32)
    state_dict["encoder.project_and_aggregate.0.bias"] = np.zeros(dim, dtype=np.float32)
    return state_dict


@pytest.fixture
def fake_torch(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Inject a minimal fake torch module into sys.modules."""
    torch = _make_fake_torch()
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "torch.nn", torch.nn)
    return torch


@pytest.fixture
def weights_file(tmp_path: Path) -> Path:
    """Write a minimal valid weights.pth file."""
    import pickle

    state_dict = _make_state_dict()
    path = tmp_path / "weights.pth"
    with path.open("wb") as f:
        pickle.dump(state_dict, f)
    return path


class TestOlmoEarthVisionEmbedder:
    def test_load_success(self, fake_torch: ModuleType, weights_file: Path) -> None:
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        embedder = OlmoEarthVisionEmbedder(str(weights_file))
        model = embedder._load()
        assert model is not None
        assert model.dim == 128

    def test_embed_shape_dtype_l2norm(self, fake_torch: ModuleType, weights_file: Path) -> None:
        from PIL import Image

        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        embedder = OlmoEarthVisionEmbedder(str(weights_file))
        images = [Image.new("RGB", (16, 16), color=(i * 40, i * 40, i * 40)) for i in range(3)]
        result = embedder.embed_images(images)

        assert result.shape == (3, 128)
        assert result.dtype == np.float32
        norms = np.linalg.norm(result, axis=1)
        assert np.allclose(norms, 1.0, atol=1e-5)

    def test_embed_empty_list(self, fake_torch: ModuleType, weights_file: Path) -> None:
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        embedder = OlmoEarthVisionEmbedder(str(weights_file))
        result = embedder.embed_images([])
        assert result.shape == (0, 128)

    def test_embed_texts_returns_none(self, fake_torch: ModuleType, weights_file: Path) -> None:
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        embedder = OlmoEarthVisionEmbedder(str(weights_file))
        assert embedder.embed_texts(["hello"]) is None

    def test_space_id(self, fake_torch: ModuleType, weights_file: Path) -> None:
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        embedder = OlmoEarthVisionEmbedder(str(weights_file))
        assert embedder.space_id == "image.olmoearth-nano-v12.v1"
        assert embedder.space_id.startswith("image.")

    def test_missing_file_error_names_path(self, fake_torch: ModuleType, tmp_path: Path) -> None:
        from geomemory.core.exceptions import ModelNotLoadedError
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        missing = tmp_path / "nonexistent.pth"
        embedder = OlmoEarthVisionEmbedder(str(missing))
        with pytest.raises(ModelNotLoadedError) as exc_info:
            embedder._load()
        assert str(missing) in str(exc_info.value)

    def test_corrupt_checkpoint_error(self, fake_torch: ModuleType, tmp_path: Path) -> None:
        from geomemory.core.exceptions import ModelNotLoadedError
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        corrupt = tmp_path / "corrupt.pth"
        corrupt.write_bytes(b"not a valid checkpoint")
        embedder = OlmoEarthVisionEmbedder(str(corrupt))
        with pytest.raises(ModelNotLoadedError) as exc_info:
            embedder._load()
        assert str(corrupt) in str(exc_info.value)

    def test_unsupported_image_type_raises(
        self,
        fake_torch: ModuleType,
        weights_file: Path,
    ) -> None:
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        embedder = OlmoEarthVisionEmbedder(str(weights_file))
        with pytest.raises(TypeError):
            embedder.embed_images([12345])  # type: ignore[list-item]


class TestOlmoEarthVisionEmbedderNoTorch:
    def test_missing_extra_error_names_vision(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When torch is not importable, importing the module should still work
        (lazy import), but attempting to load should raise an actionable error."""
        from geomemory.core.exceptions import ModelNotLoadedError

        # Block torch import
        monkeypatch.setitem(sys.modules, "torch", None)  # type: ignore[assignment]
        monkeypatch.setitem(sys.modules, "torch.nn", None)  # type: ignore[assignment]

        # Force reimport of the module
        for key in list(sys.modules.keys()):
            if key.startswith("geomemory.embeddings.olmoearth_vision"):
                del sys.modules[key]

        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        embedder = OlmoEarthVisionEmbedder(str(tmp_path / "weights.pth"))
        with pytest.raises((ImportError, ModelNotLoadedError)) as exc_info:
            embedder._load()
        msg = str(exc_info.value).lower()
        assert "torch" in msg or "vision" in msg
