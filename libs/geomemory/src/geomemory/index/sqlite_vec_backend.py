"""SqliteVecBackend — dense retrieval via sqlite-vec virtual table.

Preferred dense backend for the lightweight refactor. Vectors live inside the
workspace ``geomemory.db`` (or a sibling file) as a ``vec0`` virtual table
per embedding space (``text.onnx.<model>.v1`` → ``vec_<safe>``), so ``cp -r``
backup stays complete. Cosine distance, 384-d by default (Xenova/all-MiniLM-L6-v2).

``sqlite-vec`` is an embedded extension — no server process. Search is
``embedding MATCH ? ORDER BY distance`` and decouples inference (caller
supplies ``IndexRecord.embedding`` / ``SearchRequest.query_embedding`` produced
by an ``EmbeddingProvider``).

Fallback: when the extension is not installed or ``load()`` fails, callers
should fall back to :class:`NumpyBackend` and Doctor reports
``sqlite_vec.loadable=false``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import numpy as np

from geomemory.core.models import IndexManifest, IndexRecord, SearchHit, SearchRequest
from geomemory.embeddings.normalization import l2_normalize


def _safe_table(space_id: str) -> str:
    # vec0 table names must be valid identifiers; sanitize.
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", space_id)
    # vec0 tables cannot start with digit; prefix.
    if safe and safe[0].isdigit():
        safe = f"v_{safe}"
    return f"vec_{safe}"


def _ensure_vec_loaded(conn: sqlite3.Connection) -> None:
    """Load the sqlite-vec extension into conn; raise if unavailable."""
    try:
        import sqlite_vec  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "sqlite-vec backend requires the `sqlite-vec` package. "
            "Install with `pip install geomemory` (canonical) or `pip install sqlite-vec`."
        ) from exc
    try:
        # enable_load_extension may be disabled in some Python builds; try anyway.
        try:
            conn.enable_load_extension(True)  # type: ignore[attr-defined]
        except Exception:
            pass
        sqlite_vec.load(conn)
    except Exception as exc:  # noqa: BLE001
        raise ImportError(f"sqlite-vec extension failed to load: {exc}") from exc


class SqliteVecBackend:
    """Dense retrieval over a per-space ``vec0`` virtual table."""

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        space_id: str = "text.onnx.Xenova-all-MiniLM-L6-v2.v1",
        *,
        db_path: str | Path | None = None,
        dimension: int | None = None,
    ) -> None:
        self.space_id = space_id
        # dimension None → infer on first upsert (allows hashing 256 vs onnx 384)
        self.dimension: int | None = int(dimension) if dimension is not None else None
        self._table = _safe_table(space_id)
        self._db_path = Path(db_path) if db_path is not None else None
        self._conn = conn
        self._owns_conn = False
        if self._conn is None and self._db_path is not None:
            self._conn = sqlite3.connect(str(self._db_path))
            # WAL + foreign_keys similar to storage/connect.py
            try:
                self._conn.execute("PRAGMA journal_mode=WAL")
            except Exception:
                pass
            self._owns_conn = True

    # ── internal helpers ─────────────────────────────────────────────────

    def _conn_or_raise(self) -> sqlite3.Connection:
        if self._conn is None:
            raise ValueError("SqliteVecBackend requires a sqlite3.Connection or db_path")
        return self._conn

    def _ensure_table(self, dimension: int | None = None) -> None:
        conn = self._conn_or_raise()
        _ensure_vec_loaded(conn)
        dim = dimension if dimension is not None else self.dimension
        if dim is None:
            # Cannot create without a dimension — defer until first vector
            return
        # If table already exists with a different dimension, recreate (outside TX)
        existing = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (self._table,)
        ).fetchone()
        if existing and existing[0]:
            # sql contains float[dim]; extract dim
            import re as _re

            m = _re.search(r"float\[(\d+)\]", existing[0])
            if m and int(m.group(1)) != int(dim):
                # Dimension mismatch and table empty? Recreate. If not empty, keep existing and error later.
                cnt = 0
                try:
                    cnt = int(conn.execute(f"SELECT COUNT(*) FROM {self._table}").fetchone()[0])
                except Exception:
                    cnt = 0
                if cnt == 0:
                    conn.execute(f"DROP TABLE IF EXISTS {self._table}")
                    existing = None
                else:
                    # Keep but update self.dimension to table's dim for consistent serialize checks
                    self.dimension = int(m.group(1))
                    return
        if existing is None or not existing[0]:
            self.dimension = int(dim)
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {self._table} USING vec0("
                f"embedding float[{self.dimension}] distance_metric=cosine, "
                f"id TEXT PRIMARY KEY, chunk_text TEXT, metadata TEXT)"
            )
            conn.commit()
        else:
            # Table already exists with correct dim
            if self.dimension is None:
                import re as _re2

                m2 = _re2.search(r"float\[(\d+)\]", existing[0])
                if m2:
                    self.dimension = int(m2.group(1))

    def _serialize(self, vec: np.ndarray | list[float]) -> bytes:
        import sqlite_vec  # type: ignore[import-not-found]

        arr = np.asarray(vec, dtype=np.float32)
        if arr.ndim != 1:
            arr = arr.ravel()
        if self.dimension is None:
            self.dimension = len(arr)
        if len(arr) != self.dimension:
            if arr.shape[0] == 0:
                raise ValueError("empty embedding vector")
            raise ValueError(f"embedding dimension {len(arr)} != backend dimension {self.dimension}")
        return sqlite_vec.serialize_float32(arr.tolist())

    # ── RetrievalBackend protocol ────────────────────────────────────────

    def upsert(self, records: list[IndexRecord], embeddings: np.ndarray | None = None) -> None:
        if not records:
            return
        conn = self._conn_or_raise()
        # Infer dimension from first vector before ensuring table
        dim_hint: int | None = None
        if embeddings is not None and len(embeddings) > 0:
            dim_hint = int(np.asarray(embeddings[0]).shape[0])
        elif records and records[0].embedding is not None:
            dim_hint = int(np.asarray(records[0].embedding).shape[0])
        if self.dimension is None and dim_hint is not None:
            self.dimension = dim_hint
        self._ensure_table(dimension=self.dimension if dim_hint is None else dim_hint)
        # embeddings param: (N, D) aligned to records; fallback to record.embedding
        matrix: list[np.ndarray] | None = None
        if embeddings is not None:
            if embeddings.shape[0] != len(records):
                raise ValueError(f"embeddings rows {embeddings.shape[0]} != records {len(records)}")
            matrix = [embeddings[i] for i in range(len(records))]
        for idx, record in enumerate(records):
            vec = None
            if matrix is not None:
                vec = matrix[idx]
            elif record.embedding is not None:
                vec = np.asarray(record.embedding, dtype=np.float32)
            else:
                # No vector supplied — skip (should not happen via IndexService which embeds)
                continue
            # Normalize (cosine metric expects L2-normalized; keep consistent with provider)
            vec_n = l2_normalize(np.asarray(vec, dtype=np.float32).reshape(1, -1))[0]
            blob = self._serialize(vec_n)
            meta_json = json.dumps(record.metadata or {})
            # vec0 upsert: DELETE then INSERT (OR REPLACE not supported on vec0 PK)
            try:
                # Delete existing if any, then insert
                conn.execute(f"DELETE FROM {self._table} WHERE id = ?", (record.id,))
                conn.execute(
                    f"INSERT INTO {self._table}(id, embedding, chunk_text, metadata) VALUES (?, ?, ?, ?)",
                    (record.id, blob, record.text or "", meta_json),
                )
            except sqlite3.OperationalError as exc:
                raise RuntimeError(f"sqlite-vec upsert failed for {record.id}: {exc}") from exc
        conn.commit()

    def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        conn = self._conn_or_raise()
        # Ensure table exists (no-op if not)
        try:
            _ensure_vec_loaded(conn)
        except Exception:
            return
        # Check table existence
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (self._table,)
        ).fetchone()
        if not exists:
            return
        for _id in ids:
            conn.execute(f"DELETE FROM {self._table} WHERE id = ?", (_id,))
        conn.commit()

    def count(self) -> int:
        conn = self._conn_or_raise()
        try:
            _ensure_vec_loaded(conn)
        except Exception:
            return 0
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (self._table,)
        ).fetchone()
        if not exists:
            return 0
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {self._table}").fetchone()
            return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            return 0

    def rebuild(self, manifest: IndexManifest) -> None:
        conn = self._conn_or_raise()
        _ensure_vec_loaded(conn)
        conn.execute(f"DROP TABLE IF EXISTS {self._table}")
        conn.commit()
        # Recreate with possibly new dimension from manifest
        self.dimension = int(manifest.dimension) or self.dimension
        self._table = _safe_table(manifest.space_id)
        self.space_id = manifest.space_id
        self._ensure_table()

    def search(self, request: SearchRequest) -> list[SearchHit]:
        q = request.query_embedding
        if q is None:
            return []
        conn = self._conn_or_raise()
        try:
            _ensure_vec_loaded(conn)
        except Exception:
            return []
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (self._table,)
        ).fetchone()
        if not row or not row[0]:
            return []
        # Ensure dimension matches the declared table dimension
        if self.dimension is None:
            import re as _re

            m = _re.search(r"float\[(\d+)\]", row[0])
            if m:
                self.dimension = int(m.group(1))
        q_arr = np.asarray(q, dtype=np.float32).ravel()
        if self.dimension is not None and len(q_arr) != self.dimension:
            # If query dim mismatches table dim, cannot search — warn and return empty
            return []
        q_n = l2_normalize(q_arr.reshape(1, -1))[0]
        try:
            blob = self._serialize(q_n)
        except Exception:
            return []
        top_k = max(1, int(request.top_k or 20))
        # sqlite-vec 0.1.x: use MATCH with k hint for performance
        try:
            rows = conn.execute(
                f"SELECT id, chunk_text, metadata, distance FROM {self._table} "
                f"WHERE embedding MATCH ? AND k = ? ORDER BY distance LIMIT ?",
                (blob, top_k, top_k),
            ).fetchall()
        except sqlite3.OperationalError:
            # Fallback without k= hint
            rows = conn.execute(
                f"SELECT id, chunk_text, metadata, distance FROM {self._table} "
                f"WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
                (blob, top_k),
            ).fetchall()
        hits: list[SearchHit] = []
        for _id, text, meta_json, dist in rows:
            try:
                meta = json.loads(meta_json) if meta_json else {}
            except Exception:
                meta = {}
            # distance is cosine distance in [0,2]; similarity = 1 - distance
            try:
                d = float(dist)
            except Exception:
                d = 1.0
            # vec0 cosine distance: 1 - cosine_similarity (for normalized vectors)
            sim = 1.0 - d
            # clamp
            if sim < -1:
                sim = -1
            if sim > 1:
                sim = 1
            # filter non-positive similarity (mirrors numpy backend threshold)
            if sim <= 0:
                continue
            hits.append(
                SearchHit(
                    id=str(_id),
                    score=sim,
                    dense_score=sim,
                    text=str(text or ""),
                    locator=meta.get("locator", {}) if isinstance(meta, dict) else {},
                    metadata=meta if isinstance(meta, dict) else {},
                )
            )
        return hits[:top_k]

    # ── Persistence compat (no-op; data lives in DB) ─────────────────────

    def save(self, path: str | Path) -> None:
        # Data is already persisted in the workspace DB; create manifest file
        # for IndexService compatibility.
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        # Manifest is written by IndexService, not here.

    @classmethod
    def load(cls, path: str | Path, *, space_id: str | None = None, conn: sqlite3.Connection | None = None) -> SqliteVecBackend:
        # For IndexService.load compatibility: if a conn is supplied, use it.
        # Otherwise try to open DB at path/geomemory.db
        p = Path(path)
        if conn is not None:
            return cls(conn=conn, space_id=space_id or "text.onnx.Xenova-all-MiniLM-L6-v2.v1")
        # Heuristic: path may be indexes/<space_id> dir; find parent workspace DB
        # Search up to 3 parents for geomemory.db
        cur = p
        for _ in range(4):
            candidate = cur / "geomemory.db"
            if candidate.is_file():
                return cls(db_path=candidate, space_id=space_id or p.name)
            if cur.parent == cur:
                break
            cur = cur.parent
        # Fallback: treat path itself as DB file
        if p.is_file() and p.suffix == ".db":
            return cls(db_path=p, space_id=space_id or "text.onnx.Xenova-all-MiniLM-L6-v2.v1")
        # If no DB found, return instance with no conn — caller must supply one
        return cls(conn=None, space_id=space_id or p.name if p.name else "text.onnx.Xenova-all-MiniLM-L6-v2.v1")

    @classmethod
    def exists(cls, path: str | Path, *, conn: sqlite3.Connection | None = None, space_id: str | None = None) -> bool:
        # Exists if the vec table has rows for that space
        try:
            inst = cls.load(path, space_id=space_id, conn=conn)
            return inst.count() > 0
        except Exception:
            return False

    # Aliases for StorageBackend compatibility
    @property
    def embeddings(self) -> None:  # type: ignore[override]
        return None

    @property
    def records(self) -> list[IndexRecord]:  # type: ignore[override]
        return []
