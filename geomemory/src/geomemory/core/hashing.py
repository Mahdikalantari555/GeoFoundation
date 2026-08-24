"""SHA-256 content hashing utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Return the hex SHA-256 digest of a file, streamed to bound memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_object_path(content_hash: str) -> tuple[str, str, str]:
    """Return the (prefix_a, prefix_b, filename) components for object-store paths.

    Object store layout follows ``objects/sha256/ab/cd/<full_hash>``.
    """
    return content_hash[:2], content_hash[2:4], content_hash