"""Storage layer: SQLite, FTS5, RTree, and object store."""

from __future__ import annotations

from geomemory.storage.database import connect, initialize, integrity_check, is_healthy, schema_sql
from geomemory.storage.migrations import applied_versions, current_version, migrate
from geomemory.storage.object_store import ObjectStore

__all__ = [
    "ObjectStore",
    "applied_versions",
    "connect",
    "current_version",
    "initialize",
    "integrity_check",
    "is_healthy",
    "migrate",
    "schema_sql",
]