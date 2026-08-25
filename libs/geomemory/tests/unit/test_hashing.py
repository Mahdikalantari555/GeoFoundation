"""Unit tests for content hashing."""

from __future__ import annotations

import hashlib

from geomemory.core.hashing import hash_object_path, sha256_bytes, sha256_file


class TestSha256:
    def test_bytes_deterministic(self):
        assert sha256_bytes(b"hello") == hashlib.sha256(b"hello").hexdigest()
        assert sha256_bytes(b"hello") == sha256_bytes(b"hello")

    def test_bytes_differ(self):
        assert sha256_bytes(b"a") != sha256_bytes(b"b")

    def test_file(self, tmp_path):
        p = tmp_path / "f.txt"
        p.write_bytes(b"file content")
        assert sha256_file(p) == hashlib.sha256(b"file content").hexdigest()


class TestObjectPath:
    def test_layout(self):
        h = "ab" + "cd" + "e" * 60
        a, b, filename = hash_object_path(h)
        assert a == "ab"
        assert b == "cd"
        assert filename == h
