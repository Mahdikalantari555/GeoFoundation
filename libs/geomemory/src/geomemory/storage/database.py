"""SQLite connection management with WAL mode, foreign keys, and migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from geomemory.core.exceptions import DatabaseError

# Base schema is stored alongside this module as schema.sql.
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# PRAGMAs applied to every connection.
_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
)


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and foreign keys enabled.

    The connection is returned with ``row_factory`` set to
    :class:`sqlite3.Row` and ``detect_types`` enabled for declared types.

    ``check_same_thread`` is disabled so the connection can be reused across
    worker threads (e.g. Streamlit reruns). Callers must already serialize
    access — see :func:`thread_safe_connect` for a locked wrapper.
    """
    try:
        conn = sqlite3.connect(
            str(db_path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
    except sqlite3.Error as exc:
        raise DatabaseError(f"Failed to open database at {db_path}: {exc}") from exc
    conn.row_factory = sqlite3.Row
    try:
        for pragma in _PRAGMAS:
            conn.execute(pragma)
    except sqlite3.Error as exc:
        conn.close()
        raise DatabaseError(f"Failed to configure database: {exc}") from exc
    return conn


def schema_sql() -> str:
    """Return the raw content of schema.sql."""
    return _SCHEMA_PATH.read_text(encoding="utf-8")


def initialize(conn: sqlite3.Connection) -> None:
    """Apply the base schema (idempotent)."""
    try:
        conn.executescript(schema_sql())
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(f"Failed to initialize database schema: {exc}") from exc


def integrity_check(conn: sqlite3.Connection) -> list[str]:
    """Run ``PRAGMA integrity_check`` and return the result rows."""
    rows = conn.execute("PRAGMA integrity_check").fetchall()
    return [str(r[0]) for r in rows]


def is_healthy(conn: sqlite3.Connection) -> bool:
    """Return True if the database passes integrity_check."""
    return all(row == "ok" for row in integrity_check(conn))