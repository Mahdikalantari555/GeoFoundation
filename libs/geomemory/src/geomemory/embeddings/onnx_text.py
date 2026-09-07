"""OnnxTextEmbedder — dense text embeddings via onnxruntime + tokenizers.

Light, CPU-friendly alternative to the torch-based sentence-transformers
backend. Loads ``tokenizer.json`` + ``model.onnx`` (or ``onnx/model.onnx``)
from a local HF snapshot, mean-pools over the attention mask and L2-normalizes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


def _model_family(model_name: str) -> str:
    lower = model_name.lower()
    if "e5" in lower:
        return "e5"
    if "bge" in lower:
        return "bge"
    return "generic"


def _safe_name(model_name: str) -> str:
    return model_name.replace("/", "-").replace(".", "-")


class OnnxTextEmbedder:
    """Embed text with an ONNX export, behind the TextEmbedder shape.

    Lazy-imports ``onnxruntime``/``tokenizers``/``numpy`` so the core package
    stays light. Applies e5-family input prefixes and reports
    ``space_id=text.onnx.<safe-model>.v1`` (isolated per modality+model).
    """

    def __init__(
        self,
        model_name: str,
        *,
        model_id: str | None = None,
        model_dir: str | Path | None = None,
        offline: bool = False,
    ) -> None:
        self.model_name = model_name
        self._model_id = model_id or model_name
        self._explicit_dir = Path(model_dir) if model_dir is not None else None
        self._offline = offline
        self._session: Any = None
        self._tokenizer: Any = None
        self._family = _model_family(model_name)

    @property
    def space_id(self) -> str:
        return f"text.onnx.{_safe_name(self.model_name)}.v1"

    @property
    def model_id(self) -> str:
        return self._model_id

    # ── loading ──────────────────────────────────────────────────────────

    def _resolve_dir(self) -> Path:
        if self._explicit_dir is not None:
            return self._explicit_dir
        # Consult the hub (scan-only, no network) for a cached snapshot.
        try:
            from geomemory.embeddings.hub import EmbeddingModelHub

            hub = EmbeddingModelHub()
            found = hub.find_model(self.model_name, backend="onnx")
            if found is not None:
                return Path(found["path"])
        except Exception:  # noqa: BLE001 - hub scan is best-effort
            pass
        # Fallback: HF cache layout for onnx-community exports.
        try:
            from geomemory.embeddings.hub import _hub_cache_dir_for

            return _hub_cache_dir_for(self.model_name)
        except Exception:  # noqa: BLE001
            from pathlib import Path as _P  # noqa: N814

            return _P.home() / ".cache" / "huggingface" / "hub"

    def _ensure_downloaded(self, model_dir: Path) -> Path:
        onnx_candidates = [
            model_dir / "model.onnx",
            model_dir / "model_quantized.onnx",
            model_dir / "onnx" / "model.onnx",
            model_dir / "onnx" / "model_quantized.onnx",
        ]
        tok = model_dir / "tokenizer.json"
        if any(p.is_file() for p in onnx_candidates) and tok.is_file():
            return model_dir
        if self._offline:
            from geomemory.core.exceptions import EmbeddingUnavailableError

            raise EmbeddingUnavailableError(
                f"ONNX model '{self.model_name}' is not cached locally.",
                offline=True,
                hint="set offline=false or pre-download",
            )
        try:
            from geomemory.embeddings.hub import EmbeddingModelHub

            hub = EmbeddingModelHub()
            return Path(hub.download(self.model_name, backend="onnx"))
        except ImportError as exc:
            raise ImportError(
                "The onnx backend requires the optional `onnxruntime`, `tokenizers` "
                "and `huggingface-hub` packages. Install with `pip install geomemory[onnx]`."
            ) from exc

    def _load(self) -> tuple[Any, Any]:
        if self._session is not None and self._tokenizer is not None:
            return self._session, self._tokenizer
        try:
            import onnxruntime as ort  # type: ignore[import-not-found]
            from tokenizers import Tokenizer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "The onnx backend requires the optional `onnxruntime` and `tokenizers` "
                "packages. Install with `pip install geomemory[onnx]`."
            ) from exc
        model_dir = self._ensure_downloaded(self._resolve_dir())
        # Prefer quantized (Xenova default is onnx/model_quantized.onnx) then
        # full precision fallback.
        onnx_file = None
        for candidate in (
            model_dir / "onnx" / "model_quantized.onnx",
            model_dir / "model_quantized.onnx",
            model_dir / "onnx" / "model.onnx",
            model_dir / "model.onnx",
        ):
            if candidate.is_file():
                onnx_file = candidate
                break
        tok_file = model_dir / "tokenizer.json"
        if onnx_file is None or not tok_file.is_file():
            from geomemory.core.exceptions import EmbeddingUnavailableError

            raise EmbeddingUnavailableError(
                f"ONNX model '{self.model_name}' is incomplete at {model_dir}.",
                offline=self._offline,
                hint="set offline=false or pre-download",
            )
        self._session = ort.InferenceSession(
            str(onnx_file), providers=["CPUExecutionProvider"]
        )
        self._tokenizer = Tokenizer.from_file(str(tok_file))
        return self._session, self._tokenizer

    # ── encode ───────────────────────────────────────────────────────────

    def _apply_prefix(self, texts: Sequence[str], *, query: bool) -> list[str]:
        if self._family != "e5":
            return list(texts)
        prefix = "query: " if query else "passage: "
        return [prefix + t for t in texts]

    def _encode(self, texts: Sequence[str]) -> Any:
        import numpy as np

        session, tokenizer = self._load()
        enc = tokenizer.encode_batch(list(texts))
        input_ids = np.array([e.ids for e in enc], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids)
        inputs: dict[str, Any] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        # Only feed token_type_ids when the graph expects it.
        try:
            expected = {i.name for i in session.get_inputs()}
        except Exception:  # noqa: BLE001
            expected = set(inputs)
        if "token_type_ids" in expected:
            inputs["token_type_ids"] = token_type_ids
        outputs = session.run(None, inputs)
        last_hidden = np.asarray(outputs[0], dtype=np.float32)
        mask = attention_mask[:, :, None].astype(np.float32)
        summed = (last_hidden * mask).sum(axis=1)
        counts = mask.sum(axis=1).clip(min=1e-9)
        mean_pooled = summed / counts
        norms = np.linalg.norm(mean_pooled, axis=1, keepdims=True).clip(min=1e-12)
        return (mean_pooled / norms).astype(np.float32)

    def embed(self, texts: Sequence[str]) -> Any:
        """Embed a sequence of texts (passage path), L2-normalized."""
        return self._encode(self._apply_prefix(texts, query=False))

    def embed_query(self, texts: Sequence[str]) -> Any:
        """Embed a sequence of texts (query path), L2-normalized."""
        return self._encode(self._apply_prefix(texts, query=True))

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> Any:
        """Embed texts in batches of ``batch_size``."""
        import numpy as np

        results: list[Any] = []
        for i in range(0, len(texts), batch_size):
            results.append(self.embed(texts[i : i + batch_size]))
        if not results:
            return np.zeros((0, 0), dtype=np.float32)
        return np.concatenate(results, axis=0)

    # test hook: allow progress callbacks parity with hub.download signature
    def download_with_progress(
        self, on_progress: Callable[[float], None] | None = None
    ) -> str:
        from geomemory.embeddings.hub import EmbeddingModelHub

        return EmbeddingModelHub().download(
            self.model_name, backend="onnx", on_progress=on_progress
        )
