from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import numpy as np
import pytest

from geolearn.cache import EmbeddingCache
from geolearn.training_pipeline import TrainingPipeline


def test_pipeline_training(tmp_path: Path) -> None:
    geolearn_dir = tmp_path / "geolearn"
    geomemory_dir = tmp_path / "geomemory"
    geolearn_dir.mkdir()
    geomemory_dir.mkdir()

    with sqlite3.connect(geomemory_dir / "geomemory.db") as conn:
        conn.execute(
            """
            CREATE TABLE candidate_memory (
                id TEXT PRIMARY KEY,
                content TEXT,
                state TEXT
            )
            """
        )
        conn.commit()

    cache = EmbeddingCache(geolearn_dir)
    cache.insert("a1", np.ones(8, dtype=np.float32))
    cache.insert("a2", -np.ones(8, dtype=np.float32))

    with sqlite3.connect(geomemory_dir / "geomemory.db") as conn:
        conn.execute(
            "INSERT INTO candidate_memory VALUES (?, ?, ?)",
            ("c1", json.dumps({"asset_id": "a1", "label": 1, "crop_type": "wheat", "region": "khuzestan"}), "verified"),
        )
        conn.execute(
            "INSERT INTO candidate_memory VALUES (?, ?, ?)",
            ("c2", json.dumps({"asset_id": "a2", "label": 0, "crop_type": "wheat", "region": "khuzestan"}), "supported"),
        )
        conn.execute(
            "INSERT INTO candidate_memory VALUES (?, ?, ?)",
            ("c3", json.dumps({"asset_id": "a3", "label": 1}), "proposed"),
        )
        conn.commit()

    pipeline = TrainingPipeline(geolearn_dir, geomemory_dir)
    p = pipeline.pending_count()
    assert p["total_pending"] == 2
    assert p["by_key"]["wheat__khuzestan"] == 2

    res = pipeline.train_on_feedback()
    assert "wheat__khuzestan" in res
    assert res["wheat__khuzestan"]["samples_trained"] == 2
    assert res["wheat__khuzestan"]["total_n_samples"] == 2

    p2 = pipeline.pending_count()
    assert p2["total_pending"] == 0
