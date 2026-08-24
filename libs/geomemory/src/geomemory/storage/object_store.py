"""Content-addressed object storage keyed by SHA-256 hash.

Layout: ``<root>/sha256/ab/cd/<full_hash>``. Same content maps to the same
path, making ingestion idempotent.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from geomemory.core.hashing import hash_object_path, sha256_bytes

_ALGORITHM_DIR = "sha256"
_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class ObjectStore:
    """Filesystem-backed content-addressed store."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _object_path(self, content_hash: str) -> Path:
        a, b, filename = hash_object_path(content_hash)
        return self.root / _ALGORITHM_DIR / a / b / filename

    def put_bytes(self, data: bytes) -> str:
        """Store raw bytes, returning their SHA-256 hash."""
        content_hash = sha256_bytes(data)
        target = self._object_path(content_hash)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            # Write to temp file then rename for atomicity.
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
        return content_hash

    def put_file(self, source: str | Path) -> str:
        """Stream a file into the store, returning its SHA-256 hash."""
        source_path = Path(source)
        digest = _file_digest(source_path)
        target = self._object_path(digest)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            with source_path.open("rb") as src, tmp.open("wb") as dst:
                shutil.copyfileobj(src, dst, _CHUNK_SIZE)
            tmp.replace(target)
        return digest

    def get(self, content_hash: str) -> bytes:
        """Return the raw bytes for a content hash."""
        return self._object_path(content_hash).read_bytes()

    def get_path(self, content_hash: str) -> Path:
        """Return the filesystem path for a content hash."""
        return self._object_path(content_hash)

    def exists(self, content_hash: str) -> bool:
        """Return True if the object exists."""
        return self._object_path(content_hash).is_file()

    def delete(self, content_hash: str) -> bool:
        """Delete an object. Returns True if the object existed."""
        target = self._object_path(content_hash)
        if target.is_file():
            target.unlink()
            return True
        return False

    def size(self, content_hash: str) -> int:
        """Return the byte size of a stored object (0 if missing)."""
        target = self._object_path(content_hash)
        return target.stat().st_size if target.is_file() else 0

    def total_objects(self) -> int:
        """Return the total number of stored objects."""
        return sum(1 for p in self.root.rglob("*") if p.is_file())


def _file_digest(path: Path) -> str:
    """Stream a file and return its SHA-256 digest."""
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()