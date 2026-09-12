"""Versioned schema migration runner."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from geomemory.core.exceptions import DatabaseError


@dataclass(frozen=True)
class Migration:
    """A single versioned migration."""

    version: int
    description: str
    sql: str


# Migrations are ordered by version. The base schema is version 1.
MIGRATIONS: list[Migration] = [
    Migration(version=1, description="Initial schema (workspace, assets, segments, fts, rtree)", sql=""),
    Migration(
        version=2,
        description="Add metadata column to raster_tile",
        sql="ALTER TABLE raster_tile ADD COLUMN metadata TEXT DEFAULT '{}';",
    ),
    Migration(
        version=3,
        description="Fix spatial_index RTree to use integer rowid + entity-id map",
        sql=(
            "DROP TABLE IF EXISTS spatial_index;"
            "CREATE TABLE IF NOT EXISTS spatial_entity ("
            "    rowid     INTEGER PRIMARY KEY AUTOINCREMENT,"
            "    entity_id TEXT NOT NULL UNIQUE"
            ");"
            "CREATE VIRTUAL TABLE IF NOT EXISTS spatial_index USING rtree("
            "    id, min_lat, max_lat, min_lon, max_lon"
            ");"
        ),
    ),
    Migration(
        version=4,
        description="Add candidate_memory, knowledge_change_proposal, provenance_chain",
        sql=(
            "CREATE TABLE IF NOT EXISTS candidate_memory ("
            "    id TEXT PRIMARY KEY, content TEXT NOT NULL, memory_type TEXT NOT NULL DEFAULT 'fact',"
            "    source_feedback_ids TEXT NOT NULL DEFAULT '[]', confidence_score REAL NOT NULL DEFAULT 5.0,"
            "    state TEXT NOT NULL DEFAULT 'proposed', author TEXT, audit_trail TEXT NOT NULL DEFAULT '[]',"
            "    created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')),"
            "    CHECK (memory_type IN ('fact','correction','annotation','preference')),"
            "    CHECK (state IN ('proposed','supported','verified','rejected'))"
            ");"
            "CREATE INDEX IF NOT EXISTS idx_candidate_state ON candidate_memory(state);"
            "CREATE INDEX IF NOT EXISTS idx_candidate_score ON candidate_memory(confidence_score);"
            "CREATE TABLE IF NOT EXISTS knowledge_change_proposal ("
            "    id TEXT PRIMARY KEY, proposal_type TEXT NOT NULL, diff TEXT NOT NULL DEFAULT '{}',"
            "    source_candidate_ids TEXT NOT NULL DEFAULT '[]', confidence REAL NOT NULL DEFAULT 0.0,"
            "    status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT (datetime('now')),"
            "    reviewed_at TEXT, reviewer_id TEXT, review_note TEXT,"
            "    CHECK (proposal_type IN ('graph_relation','markdown_document','metadata_update','entity_create')),"
            "    CHECK (status IN ('pending','approved','rejected'))"
            ");"
            "CREATE INDEX IF NOT EXISTS idx_proposal_status ON knowledge_change_proposal(status);"
            "CREATE TABLE IF NOT EXISTS provenance_chain ("
            "    id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES candidate_memory(id) ON DELETE CASCADE,"
            "    feedback_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ");"
        ),
    ),
    Migration(
        version=5,
        description="Add entity table for geospatial knowledge layer",
        sql=(
            "CREATE TABLE IF NOT EXISTS entity ("
            "    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,"
            "    workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,"
            "    spatial_bbox TEXT, evidence_id TEXT,"
            "    created_at TEXT NOT NULL DEFAULT (datetime('now')),"
            "    CHECK (kind IN ('concept','location','sensor','product','stress_type','metric'))"
            ");"
            "CREATE INDEX IF NOT EXISTS idx_entity_kind ON entity(kind);"
            "CREATE INDEX IF NOT EXISTS idx_entity_workspace ON entity(workspace_id);"
            "CREATE INDEX IF NOT EXISTS idx_entity_name ON entity(name);"
        ),
    ),
]


def current_version(conn: sqlite3.Connection) -> int:
    """Return the highest applied migration version (0 if none)."""
    try:
        row = conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM schema_migration").fetchone()
    except sqlite3.Error as exc:
        raise DatabaseError(f"Failed to read schema_migration table: {exc}") from exc
    return int(row["v"]) if row is not None else 0


def applied_versions(conn: sqlite3.Connection) -> list[int]:
    """Return the list of applied migration versions."""
    rows = conn.execute("SELECT version FROM schema_migration ORDER BY version").fetchall()
    return [int(r["version"]) for r in rows]


def migrate(conn: sqlite3.Connection, schema_sql: str | None = None) -> list[int]:
    """Apply any pending migrations, returning the versions applied.

    The base schema (schema.sql) is applied first and recorded as version 1,
    then any entries in :data:`MIGRATIONS` with a higher version are applied.
    Each migration runs atomically inside a transaction.
    """
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migration (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')), description TEXT)")
    applied: list[int] = []

    if current_version(conn) == 0:
        conn.execute("BEGIN")
        try:
            if schema_sql:
                conn.executescript(schema_sql)
            conn.execute(
                "INSERT INTO schema_migration (version, description) VALUES (1, 'Initial schema')"
            )
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            conn.execute("ROLLBACK")
            raise DatabaseError(f"Migration 1 (initial schema) failed: {exc}") from exc
        applied.append(1)

    for migration in sorted(MIGRATIONS, key=lambda m: m.version):
        if migration.version <= current_version(conn):
            continue
        conn.execute("BEGIN")
        try:
            conn.executescript(migration.sql)
            conn.execute(
                "INSERT INTO schema_migration (version, description) VALUES (?, ?)",
                (migration.version, migration.description),
            )
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            conn.execute("ROLLBACK")
            raise DatabaseError(f"Migration {migration.version} ({migration.description}) failed: {exc}") from exc
        applied.append(migration.version)

    return applied
