"""Spatial repository using the RTree virtual table."""

from __future__ import annotations

import sqlite3

from geomemory.core.models import Observation, RasterScene, RasterTile, VectorLayer
from geomemory.storage.repositories.base import BaseRepository


class SpatialRepository:
    """Manage the RTree spatial index and run spatial predicates.

    The RTree stores (id, min_lat, max_lat, min_lon, max_lon) for scenes and
    segments that carry a bbox. Coordinates are EPSG:4326.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(self, entity_id: str, bbox: list[float]) -> None:
        """Insert a bbox [min_lon, min_lat, max_lon, max_lat] for an entity."""
        if len(bbox) != 4:
            raise ValueError(f"bbox must have 4 values, got {len(bbox)}")
        min_lon, min_lat, max_lon, max_lat = bbox
        rowid = self._rowid_for(entity_id, create=True)
        self.conn.execute(
            "INSERT OR REPLACE INTO spatial_index (id, min_lat, max_lat, min_lon, max_lon) "
            "VALUES (?, ?, ?, ?, ?)",
            (rowid, min_lat, max_lat, min_lon, max_lon),
        )
        self.conn.commit()

    def delete(self, entity_id: str) -> None:
        """Remove an entity from the spatial index."""
        rowid = self._rowid_for(entity_id, create=False)
        if rowid is not None:
            self.conn.execute("DELETE FROM spatial_index WHERE id = ?", (rowid,))
            self.conn.execute(
                "DELETE FROM spatial_entity WHERE entity_id = ?", (entity_id,)
            )
            self.conn.commit()

    def intersects(self, bbox: tuple[float, float, float, float]) -> list[str]:
        """Return entity ids whose bbox intersects the query bbox."""
        min_lon, min_lat, max_lon, max_lat = bbox
        rows = self.conn.execute(
            "SELECT id FROM spatial_index WHERE "
            "min_lon <= ? AND max_lon >= ? AND min_lat <= ? AND max_lat >= ?",
            (max_lon, min_lon, max_lat, min_lat),
        ).fetchall()
        return self._entities([int(r["id"]) for r in rows])

    def within(self, bbox: tuple[float, float, float, float]) -> list[str]:
        """Return entity ids fully contained within the query bbox."""
        min_lon, min_lat, max_lon, max_lat = bbox
        rows = self.conn.execute(
            "SELECT id FROM spatial_index WHERE "
            "min_lon >= ? AND max_lon <= ? AND min_lat >= ? AND max_lat <= ?",
            (min_lon, max_lon, min_lat, max_lat),
        ).fetchall()
        return self._entities([int(r["id"]) for r in rows])

    def contains(self, bbox: tuple[float, float, float, float]) -> list[str]:
        """Return entity ids whose bbox fully contains the query bbox."""
        min_lon, min_lat, max_lon, max_lat = bbox
        rows = self.conn.execute(
            "SELECT id FROM spatial_index WHERE "
            "min_lon <= ? AND max_lon >= ? AND min_lat <= ? AND max_lat >= ?",
            (min_lon, max_lon, min_lat, max_lat),
        ).fetchall()
        return self._entities([int(r["id"]) for r in rows])

    def count(self) -> int:
        """Return the number of indexed entities."""
        row = self.conn.execute("SELECT COUNT(*) AS c FROM spatial_index").fetchone()
        return int(row["c"]) if row is not None else 0

    def _rowid_for(self, entity_id: str, *, create: bool) -> int | None:
        """Return the integer rowid for an entity, optionally creating it."""
        row = self.conn.execute(
            "SELECT rowid FROM spatial_entity WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        if row is not None:
            return int(row["rowid"])
        if not create:
            return None
        cur = self.conn.execute(
            "INSERT INTO spatial_entity (entity_id) VALUES (?)", (entity_id,)
        )
        return int(cur.lastrowid)

    def _entities(self, rowids: list[int]) -> list[str]:
        """Map integer rowids back to entity TEXT ids."""
        if not rowids:
            return []
        placeholders = ",".join("?" for _ in rowids)
        rows = self.conn.execute(
            f"SELECT entity_id FROM spatial_entity WHERE rowid IN ({placeholders})",
            rowids,
        ).fetchall()
        return [str(r["entity_id"]) for r in rows]


class RasterSceneRepository(BaseRepository[RasterScene]):
    """CRUD for raster scenes."""

    table = "raster_scene"
    model_cls = RasterScene
    json_columns = ("bands", "bbox", "transform", "metadata")

    def get_by_revision(self, revision_id: str) -> list[RasterScene]:
        """Return all scenes for a revision."""
        rows = self.conn.execute(
            "SELECT * FROM raster_scene WHERE revision_id = ? ORDER BY created_at",
            (revision_id,),
        ).fetchall()
        return [self._load(r) for r in rows]

    def get_by_sensor(self, sensor: str) -> list[RasterScene]:
        """Return all scenes for a sensor."""
        rows = self.conn.execute(
            "SELECT * FROM raster_scene WHERE sensor = ? ORDER BY acquired_at", (sensor,)
        ).fetchall()
        return [self._load(r) for r in rows]

    def get_by_acquired_range(self, from_: str, to: str) -> list[RasterScene]:
        """Return scenes acquired within an ISO range."""
        rows = self.conn.execute(
            "SELECT * FROM raster_scene WHERE acquired_at >= ? AND acquired_at <= ? ORDER BY acquired_at",
            (from_, to),
        ).fetchall()
        return [self._load(r) for r in rows]


class RasterTileRepository(BaseRepository[RasterTile]):
    """CRUD for raster tiles."""

    table = "raster_tile"
    model_cls = RasterTile
    json_columns = ("window", "transform", "metadata")

    def get_by_scene(self, scene_id: str) -> list[RasterTile]:
        """Return all tiles for a scene, in creation order."""
        rows = self.conn.execute(
            "SELECT * FROM raster_tile WHERE scene_id = ? ORDER BY created_at", (scene_id,)
        ).fetchall()
        return [self._load(r) for r in rows]


class VectorLayerRepository(BaseRepository[VectorLayer]):
    """CRUD for vector layers."""

    table = "vector_layer"
    model_cls = VectorLayer
    json_columns = ("metadata",)

    def get_by_revision(self, revision_id: str) -> list[VectorLayer]:
        """Return all layers for a revision."""
        rows = self.conn.execute(
            "SELECT * FROM vector_layer WHERE revision_id = ? ORDER BY created_at", (revision_id,)
        ).fetchall()
        return [self._load(r) for r in rows]


class ObservationRepository(BaseRepository[Observation]):
    """CRUD for observations tied to a subject (scene, tile, or asset)."""

    table = "observation"
    model_cls = Observation
    json_columns = ("metadata",)

    def get_by_subject(self, subject_id: str) -> list[Observation]:
        """Return all observations for a subject."""
        rows = self.conn.execute(
            "SELECT * FROM observation WHERE subject_id = ? ORDER BY observed_at", (subject_id,)
        ).fetchall()
        return [self._load(r) for r in rows]

    def get_by_metric(self, metric: str, *, limit: int = 100) -> list[Observation]:
        """Return the most recent observations for a metric."""
        rows = self.conn.execute(
            "SELECT * FROM observation WHERE metric = ? ORDER BY observed_at DESC LIMIT ?",
            (metric, limit),
        ).fetchall()
        return [self._load(r) for r in rows]
