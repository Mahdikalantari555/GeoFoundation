"""Unit tests for the content-addressed object store."""

from __future__ import annotations

import hashlib

from geomemory.storage.object_store import ObjectStore


class TestObjectStore:
    def test_put_bytes_roundtrip(self, tmp_path):
        store = ObjectStore(tmp_path / "objects")
        h = store.put_bytes(b"hello world")
        assert store.get(h) == b"hello world"

    def test_put_bytes_deterministic(self, tmp_path):
        store = ObjectStore(tmp_path / "objects")
        h1 = store.put_bytes(b"same")
        h2 = store.put_bytes(b"same")
        assert h1 == h2
        assert store.total_objects() == 1

    def test_put_file(self, tmp_path):
        store = ObjectStore(tmp_path / "objects")
        src = tmp_path / "src.txt"
        src.write_bytes(b"file data")
        h = store.put_file(src)
        assert h == hashlib.sha256(b"file data").hexdigest()
        assert store.get(h) == b"file data"

    def test_exists(self, tmp_path):
        store = ObjectStore(tmp_path / "objects")
        h = store.put_bytes(b"x")
        assert store.exists(h)
        assert not store.exists("f" * 64)

    def test_size(self, tmp_path):
        store = ObjectStore(tmp_path / "objects")
        h = store.put_bytes(b"12345")
        assert store.size(h) == 5
        assert store.size("f" * 64) == 0

    def test_delete(self, tmp_path):
        store = ObjectStore(tmp_path / "objects")
        h = store.put_bytes(b"x")
        assert store.delete(h) is True
        assert store.exists(h) is False
        assert store.delete(h) is False

    def test_path_layout(self, tmp_path):
        store = ObjectStore(tmp_path / "objects")
        h = store.put_bytes(b"layout")
        path = store.get_path(h)
        assert path.parent.name == h[2:4]
        assert path.parent.parent.name == h[:2]
        assert path.name == h

    def test_get_missing_raises(self, tmp_path):
        store = ObjectStore(tmp_path / "objects")
        try:
            store.get("f" * 64)
            assert False, "expected FileNotFoundError"
        except FileNotFoundError:
            pass