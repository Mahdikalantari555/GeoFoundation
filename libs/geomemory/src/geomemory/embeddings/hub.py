"""EmbeddingModelHub — local scan + download orchestration for dense text models.

Filesystem scan (no DB): roots in priority order
``GEOMEMORY_EMBEDDING_ROOT`` → ``workspace embedding_path`` (if dir) →
``/mnt/data/LocalAI/Models/Embedding`` → ``~/.cache/huggingface`` →
``workspace/indexes``. Reports ``{id, name, backend, path, size_bytes,
downloaded, loadable, space_id}``. Downloads via ``huggingface_hub``
guarded by ``offline`` and a per-model pid lock.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

DEV_ROOT = Path("/mnt/data/LocalAI/Models/Embedding")
ST_CONFIG_MARKERS = ("config.json", "sentence_bert_config.json", "pytorch_model.bin")
ONNX_MARKERS = ("model.onnx", "model_quantized.onnx")
# File names accepted as an ONNX text-embedding weight file (Xenova layout
# uses onnx/model_quantized.onnx; onnx-community uses model.onnx).
ONNX_WEIGHT_FILES = (
    "model.onnx",
    "model_quantized.onnx",
    "onnx/model.onnx",
    "onnx/model_quantized.onnx",
)

# Xenova namespace hosts quantized ONNX exports (transformers.js) — light
# CPU-friendly default, e.g. Xenova/all-MiniLM-L6-v2 → onnx/model_quantized.onnx.
_ONNX_NAMESPACE_OVERRIDES: dict[str, str] = {
    "sentence-transformers/all-MiniLM-L6-v2": "Xenova/all-MiniLM-L6-v2",
    "Xenova/all-MiniLM-L6-v2": "Xenova/all-MiniLM-L6-v2",
}


def onnx_repo_for(model_name: str) -> str:
    """Return the HF repo holding the ONNX export for ``model_name``."""
    if model_name in _ONNX_NAMESPACE_OVERRIDES:
        return _ONNX_NAMESPACE_OVERRIDES[model_name]
    if model_name.startswith(("Xenova/", "onnx-community/")):
        return model_name
    if "/" in model_name:
        _, rest = model_name.split("/", 1)
        # Prefer Xenova quantized exports; fall back to onnx-community naming
        # is handled by callers trying both.
        return f"Xenova/{rest}"
    return model_name


def _safe_name(model_name: str) -> str:
    return model_name.replace("/", "-").replace(".", "-")


def _hub_cache_dir_for(model_name: str) -> Path:
    root = Path(os.environ.get("GEOMEMORY_EMBEDDING_ROOT", "") or Path.home() / ".cache")
    return root / "huggingface" / "hub" / ("models--" + model_name.replace("/", "--"))


def _dir_size(path: Path, *, max_files: int = 2000) -> int:
    total = 0
    count = 0
    try:
        for p in path.rglob("*"):
            if count >= max_files:
                break
            try:
                if p.is_file():
                    # Only count model-relevant files.
                    if p.suffix in (".bin", ".onnx", ".json", ".safetensors", ".txt"):
                        total += p.stat().st_size
                    count += 1
            except OSError:
                continue
    except OSError:
        pass
    return total


def _classify_dir(path: Path) -> str | None:
    """Return 'onnx' | 'st' if dir looks like a text embedding model, else None."""
    try:
        names = {p.name for p in path.iterdir()}
    except OSError:
        return None
    # ONNX first: any known weight file at top level or under onnx/.
    if (path / "model.onnx").is_file() or (path / "model_quantized.onnx").is_file():
        return "onnx"
    try:
        onnx_sub = path / "onnx"
        if onnx_sub.is_dir():
            sub_names = {p.name for p in onnx_sub.iterdir()}
            if "model.onnx" in sub_names or "model_quantized.onnx" in sub_names:
                return "onnx"
    except OSError:
        pass
    if "tokenizer.json" in names and "config.json" in names:
        # Tokenizer + config without an ONNX weight is an ST checkout.
        return "st"
    if "config.json" in names or "sentence_bert_config.json" in names:
        # Exclude vision-style dirs (weights.pth without text config).
        cfg = path / "config.json"
        try:
            if cfg.is_file():
                text = cfg.read_text(encoding="utf-8", errors="ignore")[:2000].lower()
                if "vision" in text and "text" not in text and "bert" not in text:
                    return None
        except OSError:
            pass
        return "st"
    if (path / "pytorch_model.bin").is_file():
        return "st"
    return None


class EmbeddingModelHub:
    """Scan local roots and download missing models on demand."""

    def __init__(
        self,
        *,
        extra_roots: list[str | Path] | None = None,
        workspace_dir: str | Path | None = None,
        embedding_path: str | Path | None = None,
    ) -> None:
        self._extra_roots = [Path(r) for r in (extra_roots or [])]
        self._workspace_dir = Path(workspace_dir) if workspace_dir else None
        self._embedding_path = Path(embedding_path) if embedding_path else None

    # ── roots ────────────────────────────────────────────────────────────

    def roots(self) -> list[Path]:
        ordered: list[Path] = []
        env = os.environ.get("GEOMEMORY_EMBEDDING_ROOT")
        if env:
            ordered.append(Path(env).expanduser())
        if self._embedding_path is not None:
            ordered.append(self._embedding_path)
        for r in self._extra_roots:
            ordered.append(r)
        ordered.append(DEV_ROOT)
        ordered.append(Path.home() / ".cache" / "huggingface")
        if self._workspace_dir is not None:
            ordered.append(self._workspace_dir / "indexes")
        # Dedupe, keep order.
        seen: set[str] = set()
        out: list[Path] = []
        for r in ordered:
            key = str(r)
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out

    # ── scan ─────────────────────────────────────────────────────────────

    def scan(self) -> list[dict[str, Any]]:
        entries: dict[str, dict[str, Any]] = {}
        for root in self.roots():
            if not root.is_dir():
                continue
            # HF cache layout: hub/models--org--name/snapshots/<sha>/
            if root.name == "huggingface" or "huggingface" in str(root):
                self._scan_hf_cache(root, entries)
            self._scan_flat(root, entries)
        return sorted(entries.values(), key=lambda e: str(e["name"]))

    def _register(
        self, entries: dict[str, dict[str, Any]], name: str, path: Path, backend: str
    ) -> None:
        key = f"{backend}:{name}"
        if key in entries:
            return
        size = _dir_size(path) if path.is_dir() else 0
        space = f"text.{'onnx' if backend == 'onnx' else 'st'}.{_safe_name(name)}.v1"
        entries[key] = {
            "id": key,
            "name": name,
            "backend": backend,
            "path": str(path),
            "size_bytes": size,
            "downloaded": True,
            "loadable": True,
            "space_id": space,
        }

    def _scan_flat(self, root: Path, entries: dict[str, dict[str, Any]]) -> None:
        try:
            children = list(root.iterdir())
        except OSError:
            return
        for child in children:
            if not child.is_dir():
                continue
            if child.name.startswith("models--"):
                continue  # handled by HF scan
            backend = _classify_dir(child)
            if backend is not None:
                self._register(entries, child.name, child, backend)
            else:
                # One level deeper (e.g. Embedding/V1.2_Nano is vision → skipped).
                try:
                    for grand in child.iterdir():
                        if not grand.is_dir():
                            continue
                        b2 = _classify_dir(grand)
                        if b2 is not None:
                            self._register(
                                entries, f"{child.name}/{grand.name}", grand, b2
                            )
                except OSError:
                    continue

    def _scan_hf_cache(self, root: Path, entries: dict[str, dict[str, Any]]) -> None:
        hub = root / "hub" if root.name == ".cache" or (root / "hub").is_dir() else root
        if not hub.is_dir():
            # root itself may be .../.cache/huggingface
            hub = root / "hub" if root.name != "hub" else root
        if not hub.is_dir():
            return
        try:
            for child in hub.iterdir():
                if not child.is_dir() or not child.name.startswith("models--"):
                    continue
                model_name = child.name[len("models--") :].replace("--", "/")
                snapshots = child / "snapshots"
                target = snapshots
                if snapshots.is_dir():
                    try:
                        snaps = sorted(
                            [p for p in snapshots.iterdir() if p.is_dir()],
                            key=lambda p: p.stat().st_mtime,
                        )
                        if snaps:
                            target = snaps[-1]
                    except OSError:
                        pass
                else:
                    target = child
                backend = _classify_dir(target)
                if backend is None:
                    # snapshot may nest one level; check children
                    try:
                        for sub in target.iterdir():
                            if sub.is_dir():
                                backend = _classify_dir(sub)
                                if backend is not None:
                                    target = sub
                                    break
                    except OSError:
                        pass
                if backend is not None:
                    self._register(entries, model_name, target, backend)
        except OSError:
            return

    def find_model(self, model_name: str, *, backend: str = "st") -> dict[str, Any] | None:
        for entry in self.scan():
            if entry["name"] == model_name and entry["backend"] == backend:
                return entry
            # HF cache name match with different separator.
            if entry["name"].replace("--", "/") == model_name and entry["backend"] == backend:
                return entry
        return None

    def summary(
        self, *, active_backend: str | None = None, active_model: str | None = None
    ) -> dict[str, Any]:
        models = self.scan()
        downloaded = sum(1 for m in models if m.get("downloaded"))
        active_space: str | None = None
        if active_backend and active_model:
            prefix = "onnx" if active_backend == "onnx" else "st"
            active_space = f"text.{prefix}.{_safe_name(active_model)}.v1"
        return {
            "hub_count": len(models),
            "downloaded": downloaded,
            "active_backend": active_backend,
            "active_model": active_model,
            "active_space_id": active_space,
        }

    # ── download ─────────────────────────────────────────────────────────

    def download(
        self,
        model_name: str,
        *,
        backend: str = "st",
        offline: bool = False,
        on_progress: Callable[[float], None] | None = None,
    ) -> str:
        """Download ``model_name`` via huggingface_hub; return the local dir.

        Reuses an in-flight pid lock: a second concurrent call returns the
        existing path once the lock clears.
        """
        existing = self.find_model(model_name, backend=backend)
        if existing is not None:
            if on_progress is not None:
                on_progress(1.0)
            return str(existing["path"])
        if offline or os.environ.get("GEOMEMORY_OFFLINE", "").lower() in ("1", "true"):
            from geomemory.core.exceptions import EmbeddingUnavailableError

            raise EmbeddingUnavailableError(
                f"Model '{model_name}' is not cached locally.",
                offline=True,
                hint="set offline=false or pre-download",
            )
        try:
            from huggingface_hub import snapshot_download  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "Model download requires the optional `huggingface-hub` package. "
                "Install with `pip install geomemory[onnx]` or `geomemory[st]`."
            ) from exc

        repo = onnx_repo_for(model_name) if backend == "onnx" else model_name
        cache_root = os.environ.get("GEOMEMORY_EMBEDDING_ROOT") or os.environ.get(
            "HF_HOME", str(Path.home() / ".cache" / "huggingface")
        )
        lock_file = Path(cache_root) / (f".lock-{_safe_name(model_name)}-{backend}.pid")
        try:
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            if lock_file.is_file():
                # Another download may be in flight; fall through to snapshot_download
                # which is itself cached/idempotent.
                pass
            else:
                with contextlib.suppress(OSError):
                    lock_file.write_text(str(os.getpid()), encoding="utf-8")
            allow = (
                ("*.onnx", "onnx/*.onnx", "tokenizer.json", "tokenizer_config.json", "config.json")
                if backend == "onnx"
                else None
            )
            local = snapshot_download(
                repo_id=repo,
                cache_dir=cache_root,
                allow_patterns=list(allow) if allow else None,
            )
            if on_progress is not None:
                on_progress(1.0)
            return str(local)
        finally:
            try:
                if lock_file.is_file():
                    lock_file.unlink()
            except OSError:
                pass
