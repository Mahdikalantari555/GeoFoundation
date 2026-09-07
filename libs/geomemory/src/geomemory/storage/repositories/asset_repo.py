"""Asset and revision repository."""

from __future__ import annotations

from geomemory.core.models import Asset, AssetRevision
from geomemory.storage.repositories.base import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    """CRUD for assets."""

    table = "asset"
    model_cls = Asset
    json_columns = ("metadata",)

    def get_by_collection(self, collection_id: str) -> list[Asset]:
        """Return all non-deleted assets in a collection."""
        rows = self.conn.execute(
            "SELECT * FROM asset WHERE collection_id = ? AND deleted_at IS NULL ORDER BY created_at",
            (collection_id,),
        ).fetchall()
        return [self._load(r) for r in rows]

    def get_by_kind(self, kind: str) -> list[Asset]:
        """Return all non-deleted assets of a kind."""
        rows = self.conn.execute(
            "SELECT * FROM asset WHERE kind = ? AND deleted_at IS NULL ORDER BY created_at",
            (kind,),
        ).fetchall()
        return [self._load(r) for r in rows]

    def soft_delete(self, asset_id: str) -> bool:
        """Soft-delete an asset (sets deleted_at)."""
        cur = self.conn.execute(
            "UPDATE asset SET deleted_at = datetime('now') WHERE id = ? AND deleted_at IS NULL",
            (asset_id,),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def set_current_revision(self, asset_id: str, revision_id: str) -> None:
        """Update the current revision pointer of an asset."""
        self.conn.execute(
            "UPDATE asset SET current_revision_id = ? WHERE id = ?", (revision_id, asset_id)
        )
        self.conn.commit()


class AssetRevisionRepository(BaseRepository[AssetRevision]):
    """CRUD for asset revisions."""

    table = "asset_revision"
    model_cls = AssetRevision
    json_columns = ("metadata",)

    def get_by_hash(self, content_hash: str) -> AssetRevision | None:
        """Return the first revision with a given content hash."""
        row = self.conn.execute(
            "SELECT * FROM asset_revision WHERE hash = ? LIMIT 1", (content_hash,)
        ).fetchone()
        return self._load(row) if row is not None else None

    def get_by_asset(self, asset_id: str) -> list[AssetRevision]:
        """Return all revisions of an asset, newest first."""
        rows = self.conn.execute(
            "SELECT * FROM asset_revision WHERE asset_id = ? ORDER BY ingested_at DESC",
            (asset_id,),
        ).fetchall()
        return [self._load(r) for r in rows]

    def list_hashes(self) -> list[str]:
        """Return all stored content hashes."""
        rows = self.conn.execute("SELECT hash FROM asset_revision").fetchall()
        return [str(r["hash"]) for r in rows]
