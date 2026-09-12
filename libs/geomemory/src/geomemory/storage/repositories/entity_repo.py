"""Entity repository — CRUD for the entity knowledge table."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from geomemory.core.models import Entity
from geomemory.storage.repositories.base import BaseRepository


class EntityRepository(BaseRepository[Entity]):
    """CRUD for the entity table."""

    table = "entity"
    model_cls = Entity
    json_columns = ("spatial_bbox", "metadata")

    def create(self, entity: Entity) -> Entity:
        """Insert an entity row. Returns the same instance."""
        data = self._dump(entity)
        self.conn.execute(
            "INSERT INTO entity (id, name, kind, workspace_id, spatial_bbox, evidence_id, created_at) "
            "VALUES (:id, :name, :kind, :workspace_id, :spatial_bbox, :evidence_id, :created_at)",
            {
                "id": entity.id,
                "name": entity.name,
                "kind": entity.kind,
                "workspace_id": entity.workspace_id or "",
                "spatial_bbox": json.dumps(entity.spatial_bbox) if entity.spatial_bbox else None,
                "evidence_id": entity.evidence_id,
                "created_at": entity.created_at,
            },
        )
        self.conn.commit()
        return entity

    def upsert_name_match(self, name: str, kind: str, workspace_id: str, *, evidence_id: str | None = None) -> Entity:
        """Return existing entity matching (name, kind) or insert a new one."""
        row = self.conn.execute(
            "SELECT * FROM entity WHERE name = ? AND kind = ? AND workspace_id = ? LIMIT 1",
            (name, kind, workspace_id),
        ).fetchone()
        if row is not None:
            return self._load(row)
        entity = Entity(name=name, kind=kind, workspace_id=workspace_id, evidence_id=evidence_id)
        return self.create(entity)

    def list_by_kind(self, kind: str, *, workspace_id: str | None = None, limit: int = 100) -> list[Entity]:
        """Return entities of a given kind, optionally scoped to a workspace."""
        sql = "SELECT * FROM entity WHERE kind = ?"
        params: list[Any] = [kind]
        if workspace_id:
            sql += " AND workspace_id = ?"
            params.append(workspace_id)
        sql += " ORDER BY created_at LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [self._load(r) for r in rows]

    def list_by_workspace(self, workspace_id: str, limit: int = 1000) -> list[Entity]:
        """Return all entities for a workspace."""
        rows = self.conn.execute(
            "SELECT * FROM entity WHERE workspace_id = ? ORDER BY kind, name LIMIT ?",
            (workspace_id, limit),
        ).fetchall()
        return [self._load(r) for r in rows]

    def count(self) -> int:
        """Return the number of rows."""
        row = self.conn.execute("SELECT COUNT(*) AS c FROM entity").fetchone()
        return int(row["c"]) if row is not None else 0

    def get_by_evidence(self, evidence_id: str) -> list[Entity]:
        """Return entities whose evidence_id matches."""
        rows = self.conn.execute(
            "SELECT * FROM entity WHERE evidence_id = ?", (evidence_id,)
        ).fetchall()
        return [self._load(r) for r in rows]
