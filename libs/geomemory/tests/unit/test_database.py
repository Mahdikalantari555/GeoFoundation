"""Unit tests for the SQLite storage layer."""

from __future__ import annotations

import sqlite3

from geomemory.storage.database import connect, initialize, integrity_check, is_healthy, schema_sql
from geomemory.storage.migrations import applied_versions, current_version, migrate


class TestConnect:
    def test_creates_file(self, tmp_path):
        db = tmp_path / "test.db"
        conn = connect(db)
        assert db.exists()
        conn.close()

    def test_wal_mode(self, tmp_path):
        conn = connect(tmp_path / "test.db")
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_foreign_keys_on(self, tmp_path):
        conn = connect(tmp_path / "test.db")
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()

    def test_row_factory(self, tmp_path):
        conn = connect(tmp_path / "test.db")
        assert conn.row_factory is sqlite3.Row
        conn.close()

    def test_usable_from_other_thread(self, tmp_path):
        """Regression: a connection must work from a different OS thread.

        Streamlit reruns each execute in a fresh thread, which surfaced
        ``SQLite objects created in a thread can only be used in that same
        thread`` when the connection was bound to its creating thread.
        """
        import threading

        conn = connect(tmp_path / "test.db")
        initialize(conn)
        conn.execute("INSERT INTO workspace (id, name, created_at) VALUES ('ws1', 'W', '2024-01-01T00:00:00Z')")
        conn.commit()

        result = {}

        def worker() -> None:
            row = conn.execute("SELECT name FROM workspace WHERE id='ws1'").fetchone()
            result["name"] = row["name"]

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        assert result["name"] == "W"
        conn.close()


class TestSchema:
    def test_schema_sql_nonempty(self):
        assert "CREATE TABLE" in schema_sql()

    def test_initialize_creates_tables(self, tmp_path):
        conn = connect(tmp_path / "test.db")
        initialize(conn)
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "workspace" in tables
        assert "asset" in tables
        assert "segment" in tables
        assert "job" in tables
        assert "schema_migration" in tables
        conn.close()

    def test_initialize_idempotent(self, tmp_path):
        conn = connect(tmp_path / "test.db")
        initialize(conn)
        initialize(conn)  # should not raise
        conn.close()

    def test_fts5_table(self, tmp_path):
        conn = connect(tmp_path / "test.db")
        initialize(conn)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='segments_fts'"
        ).fetchone()
        assert row is not None
        conn.close()

    def test_rtree_table(self, tmp_path):
        conn = connect(tmp_path / "test.db")
        initialize(conn)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='spatial_index'"
        ).fetchone()
        assert row is not None
        conn.close()


class TestMigrations:
    def test_initial_migration(self, tmp_path):
        conn = connect(tmp_path / "test.db")
        applied = migrate(conn, schema_sql())
        assert 1 in applied
        assert 2 in applied  # raster_tile.metadata column migration
        assert 3 in applied  # spatial_index rowid fix migration
        assert current_version(conn) == 3
        assert applied_versions(conn) == [1, 2, 3]
        conn.close()

    def test_migrate_idempotent(self, tmp_path):
        conn = connect(tmp_path / "test.db")
        migrate(conn, schema_sql())
        applied = migrate(conn, schema_sql())
        assert applied == []
        conn.close()


class TestIntegrity:
    def test_healthy(self, tmp_path):
        conn = connect(tmp_path / "test.db")
        initialize(conn)
        assert is_healthy(conn)
        assert integrity_check(conn) == ["ok"]
        conn.close()
