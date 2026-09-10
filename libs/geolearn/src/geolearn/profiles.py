from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class UserProfile:
    user_id: str
    region: str
    crop_type: str = "unknown"
    preferred_classifier: str = "sgd"
    trained_at: str | None = None
    n_training_samples: int = 0


class ProfileStore:
    """Persistent profile storage mapping (user_id, region) to UserProfile in SQLite."""

    def __init__(self, workspace_dir: str | Path) -> None:
        self.workspace_dir = Path(workspace_dir)
        if self.workspace_dir.suffix == ".db":
            self.db_path = self.workspace_dir
            self.workspace_dir = self.workspace_dir.parent
        else:
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = self.workspace_dir / "geolearn.db"
        self._migrate()

    def _migrate(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT NOT NULL,
                    region TEXT NOT NULL,
                    crop_type TEXT NOT NULL DEFAULT 'unknown',
                    preferred_classifier TEXT NOT NULL DEFAULT 'sgd',
                    trained_at TEXT,
                    n_training_samples INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, region)
                )
                """
            )
            conn.commit()

    def get(self, user_id: str, region: str) -> UserProfile | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT user_id, region, crop_type, preferred_classifier, trained_at, n_training_samples
                FROM user_profiles
                WHERE user_id = ? AND region = ?
                """,
                (user_id, region),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return UserProfile(
                user_id=row[0],
                region=row[1],
                crop_type=row[2],
                preferred_classifier=row[3],
                trained_at=row[4],
                n_training_samples=int(row[5]),
            )

    def get_or_create(self, user_id: str, region: str) -> UserProfile:
        existing = self.get(user_id, region)
        if existing is not None:
            return existing
        profile = UserProfile(user_id=user_id, region=region)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO user_profiles (
                    user_id, region, crop_type, preferred_classifier, trained_at, n_training_samples
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.user_id,
                    profile.region,
                    profile.crop_type,
                    profile.preferred_classifier,
                    profile.trained_at,
                    profile.n_training_samples,
                ),
            )
            conn.commit()
        loaded = self.get(user_id, region)
        return loaded if loaded is not None else profile

    def update(self, user_id: str, region: str, **fields: Any) -> UserProfile:
        profile = self.get_or_create(user_id, region)
        valid_fields = {
            "crop_type",
            "preferred_classifier",
            "trained_at",
            "n_training_samples",
        }
        updates: dict[str, Any] = {}
        for k, v in fields.items():
            if k in valid_fields:
                if k == "n_training_samples":
                    v = int(v)
                elif k in ("crop_type", "preferred_classifier"):
                    v = str(v)
                updates[k] = v
                setattr(profile, k, v)
        if updates:
            set_clauses = [f"{k} = ?" for k in updates]
            values = list(updates.values()) + [user_id, region]
            clause_str = ", ".join(set_clauses)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f"UPDATE user_profiles SET {clause_str} WHERE user_id = ? AND region = ?",
                    values,
                )
                conn.commit()
        return profile

    def list_all(self) -> list[UserProfile]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT user_id, region, crop_type, preferred_classifier, trained_at, n_training_samples
                FROM user_profiles
                ORDER BY user_id, region
                """
            )
            return [
                UserProfile(
                    user_id=row[0],
                    region=row[1],
                    crop_type=row[2],
                    preferred_classifier=row[3],
                    trained_at=row[4],
                    n_training_samples=int(row[5]),
                )
                for row in cursor.fetchall()
            ]
