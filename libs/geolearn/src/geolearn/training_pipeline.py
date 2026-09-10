from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from geolearn.cache import EmbeddingCache
from geolearn.persistence import ClassifierStore


class TrainingPipeline:
    def __init__(self, geolearn_dir: str | Path, geomemory_workspace: str | Path) -> None:
        self.geolearn_dir = Path(geolearn_dir)
        self.geomemory_workspace = Path(geomemory_workspace)
        self.geolearn_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.geolearn_dir / "geolearn.db"
        self.cache = EmbeddingCache(self.geolearn_dir)
        self.store = ClassifierStore(self.geolearn_dir)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trained_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    trained_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS training_log (
                    id TEXT PRIMARY KEY,
                    key_crop TEXT NOT NULL,
                    key_region TEXT NOT NULL,
                    n_samples INTEGER NOT NULL,
                    trained_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _get_geomemory_db_path(self) -> Path:
        if (self.geomemory_workspace / "geomemory.db").exists():
            return self.geomemory_workspace / "geomemory.db"
        if (self.geomemory_workspace / "workspace.db").exists():
            return self.geomemory_workspace / "workspace.db"
        return self.geomemory_workspace / "geomemory.db"

    def _get_pending_candidates(
        self, feedback_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        gm_db = self._get_geomemory_db_path()
        if not gm_db.exists():
            return []

        trained_ids: set[str] = set()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT candidate_id FROM trained_candidates")
            trained_ids = {row[0] for row in cursor}

        candidates: list[dict[str, Any]] = []
        with sqlite3.connect(gm_db) as conn:
            cursor = conn.execute(
                "SELECT id, content, state FROM candidate_memory WHERE state IN ('verified', 'supported')"
            )
            for cid, content, _ in cursor:
                if cid in trained_ids:
                    continue
                if feedback_ids is not None and cid not in feedback_ids:
                    continue

                try:
                    data = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    data = {"asset_id": cid, "label": 0}

                candidates.append({
                    "id": cid,
                    "asset_id": data.get("asset_id", cid),
                    "label": int(data.get("label", 0)),
                    "crop_type": data.get("crop_type", "unknown"),
                    "region": data.get("region", "global"),
                })
        return candidates

    def pending_count(self) -> dict[str, Any]:
        candidates = self._get_pending_candidates()
        by_key: dict[str, int] = {}
        for c in candidates:
            k = f"{c['crop_type']}__{c['region']}"
            by_key[k] = by_key.get(k, 0) + 1
        return {"total_pending": len(candidates), "by_key": by_key}

    def train_on_feedback(
        self, feedback_ids: list[str] | None = None, batch_size: int = 10
    ) -> dict[str, dict[str, int]]:
        candidates = self._get_pending_candidates(feedback_ids=feedback_ids)
        if not candidates:
            return {}

        by_key_candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for c in candidates:
            key = (c["crop_type"], c["region"])
            by_key_candidates.setdefault(key, []).append(c)

        result: dict[str, dict[str, int]] = {}
        now = datetime.now(timezone.utc).isoformat()

        for key, items in by_key_candidates.items():
            clf = self.store.get_classifier(key)
            X_list: list[np.ndarray] = []
            y_list: list[int] = []
            valid_cids: list[str] = []

            for item in items:
                emb = self.cache.lookup(item["asset_id"])
                if emb is None:
                    continue
                X_list.append(emb)
                y_list.append(item["label"])
                valid_cids.append(item["id"])

            if not X_list:
                continue

            for i in range(0, len(X_list), batch_size):
                batch_X = np.array(X_list[i : i + batch_size], dtype=np.float32)
                batch_y = np.array(y_list[i : i + batch_size], dtype=np.int64)
                clf.partial_fit(batch_X, batch_y)

            crop, region = key
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute(
                    "SELECT n_samples FROM classifier_state WHERE key_crop = ? AND key_region = ?",
                    (crop, region),
                )
                row = cur.fetchone()
                prior_samples = row[0] if row else 0
                total_samples = prior_samples + len(X_list)

            self.store.save_classifier(key, clf, n_samples=total_samples)

            with sqlite3.connect(self.db_path) as conn:
                for cid in valid_cids:
                    conn.execute(
                        "INSERT OR IGNORE INTO trained_candidates (candidate_id, trained_at) VALUES (?, ?)",
                        (cid, now),
                    )
                conn.execute(
                    "INSERT INTO training_log (id, key_crop, key_region, n_samples, trained_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), crop, region, len(X_list), now),
                )
                conn.commit()

            k_str = f"{crop}__{region}"
            result[k_str] = {
                "samples_trained": len(X_list),
                "total_n_samples": total_samples,
            }

        return result
