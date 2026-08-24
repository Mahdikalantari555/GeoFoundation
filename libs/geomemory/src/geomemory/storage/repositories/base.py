"""Base repository class shared by all entity repositories."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, ClassVar, Generic, TypeVar

from geomemory.core.models import GeoMemoryModel

T = TypeVar("T", bound=GeoMemoryModel)


class BaseRepository(Generic[T]):
    """Generic CRUD base bound to a table with JSON columns.

    Subclasses must set ``table``, ``model_cls`` and, when needed,
    ``json_columns`` (columns stored as JSON TEXT).
    """

    table: ClassVar[str] = ""
    model_cls: ClassVar[type[GeoMemoryModel]]
    json_columns: ClassVar[tuple[str, ...]] = ("metadata",)

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _dump(self, model: T) -> dict[str, Any]:
        """Convert a model to a DB row dict with JSON stringification."""
        data = model.model_dump()
        for col in self.json_columns:
            if col in data:
                data[col] = json.dumps(data[col], ensure_ascii=False)
        return data

    def _load(self, row: sqlite3.Row) -> T:
        """Convert a DB row back to a model, parsing JSON columns."""
        data = dict(row)
        for col in self.json_columns:
            if col in data and isinstance(data[col], str):
                data[col] = json.loads(data[col])
        return self.model_cls(**data)  # type: ignore[return-value]

    def insert(self, model: T) -> T:
        """Insert a model row (upsert on conflict)."""
        data = self._dump(model)
        cols = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data)
        sql = (
            f"INSERT INTO {self.table} ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET "
            + ", ".join(f"{k}=excluded.{k}" for k in data if k != "id")
        )
        self.conn.execute(sql, data)
        self.conn.commit()
        return model

    def get(self, id: str) -> T | None:
        """Fetch a row by primary key id, or None."""
        row = self.conn.execute(f"SELECT * FROM {self.table} WHERE id = ?", (id,)).fetchone()
        return self._load(row) if row is not None else None

    def delete(self, id: str) -> bool:
        """Delete a row by id. Returns True if a row was deleted."""
        cur = self.conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (id,))
        self.conn.commit()
        return cur.rowcount > 0

    def list_all(self, limit: int = 1000) -> list[T]:
        """Return up to ``limit`` rows."""
        rows = self.conn.execute(f"SELECT * FROM {self.table} LIMIT ?", (limit,)).fetchall()
        return [self._load(r) for r in rows]

    def count(self) -> int:
        """Return the number of rows."""
        row = self.conn.execute(f"SELECT COUNT(*) AS c FROM {self.table}").fetchone()
        return int(row["c"]) if row is not None else 0