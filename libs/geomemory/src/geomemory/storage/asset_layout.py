"""AssetLayout — logical asset directory layout over content-addressed ObjectStore."""

from __future__ import annotations

from pathlib import Path

from geomemory.core.hashing import hash_object_path

_KIND_DIRS: dict[str, str] = {
    "document": "assets/documents",
    "code": "assets/documents",
    "raster": "assets/imagery",
    "imagery": "assets/imagery",
    "vector": "assets/vectors",
    "table": "assets/datasets",
    "dataset": "assets/datasets",
    "datasets": "assets/datasets",
}


def _logical_dir(kind: str) -> str:
    return _KIND_DIRS.get(kind, "assets/documents")


class AssetLayout:
    """Map logical asset paths to content-addressed physical paths.

    Logical:  assets/documents/ab/cd/<sha256>  etc.
    Physical: objects/sha256/ab/cd/<sha256>
    """

    def __init__(self, workspace_root: str | Path) -> None:
        self.root = Path(workspace_root)

    def logical_path(self, content_hash: str, kind: str = "document") -> str:
        """Return logical path for a hash and kind."""
        a, b, _ = hash_object_path(content_hash)
        return f"{_logical_dir(kind)}/{a}/{b}/{content_hash}"

    def physical_path(self, content_hash: str) -> Path:
        """Return physical ObjectStore path for a hash."""
        a, b, filename = hash_object_path(content_hash)
        return self.root / "objects" / "sha256" / a / b / filename

    def resolve(self, content_hash: str, kind: str = "document") -> Path:
        """Resolve logical asset to physical path (content-addressed)."""
        return self.physical_path(content_hash)

    def kind_for_logical(self, logical_path: str) -> str:
        """Infer kind from logical path prefix."""
        if logical_path.startswith("assets/imagery"):
            return "raster"
        if logical_path.startswith("assets/vectors"):
            return "vector"
        if logical_path.startswith("assets/datasets"):
            return "table"
        return "document"
