import io
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np


class EmbeddingCache:
    def __init__(self, workspace_dir: str | Path) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.workspace_dir / "geolearn.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    asset_id TEXT PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    label INTEGER
                )
                """
            )
            try:
                conn.execute("ALTER TABLE embedding_cache ADD COLUMN label INTEGER")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def insert(
        self,
        asset_id: str,
        vector: np.ndarray | list[float],
        label: int | None = None,
    ) -> None:
        vec_f32 = np.asarray(vector, dtype=np.float32)
        buf = io.BytesIO()
        joblib.dump(vec_f32, buf)
        blob = buf.getvalue()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO embedding_cache (asset_id, embedding, created_at, label)
                VALUES (?, ?, ?, ?)
                """,
                (asset_id, blob, now, label),
            )
            conn.commit()

    def set_label(self, asset_id: str, label: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE embedding_cache SET label = ? WHERE asset_id = ?",
                (label, asset_id),
            )
            conn.commit()

    def get_label(self, asset_id: str) -> int | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT label FROM embedding_cache WHERE asset_id = ?", (asset_id,)
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                return None
            return int(row[0])

    def lookup(self, asset_id: str) -> np.ndarray | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT embedding FROM embedding_cache WHERE asset_id = ?", (asset_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            buf = io.BytesIO(row[0])
            arr = joblib.load(buf)
            return np.asarray(arr, dtype=np.float32)

    def nn_lookup(
        self, vector: np.ndarray | list[float], k: int = 3
    ) -> list[tuple[str, float]]:
        vec_f32 = np.asarray(vector, dtype=np.float32)
        results: list[tuple[str, float]] = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT asset_id, embedding FROM embedding_cache")
            for asset_id, blob in cursor:
                buf = io.BytesIO(blob)
                cand = joblib.load(buf)
                dist = float(np.linalg.norm(vec_f32 - cand))
                results.append((asset_id, dist))
        results.sort(key=lambda x: x[1])
        return results[:k]
