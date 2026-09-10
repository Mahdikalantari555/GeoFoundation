from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class UserSettings:
    user_id: str
    confidence_threshold: float = 0.6
    preferred_classifier: str = "sgd"
    auto_train_on_feedback: bool = True
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class UserSettingsStore:
    """Persistent user settings storage for confidence threshold and learning preferences."""

    def __init__(self, workspace_dir: str | Path) -> None:
        self.workspace_dir = Path(workspace_dir)
        if self.workspace_dir.suffix == ".db":
            self.db_path = self.workspace_dir
            self.workspace_dir = self.workspace_dir.parent
        else:
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = self.workspace_dir / "geolearn.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    confidence_threshold REAL NOT NULL DEFAULT 0.6,
                    preferred_classifier TEXT NOT NULL DEFAULT 'sgd',
                    auto_train_on_feedback BOOLEAN NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_or_default(self, user_id: str) -> UserSettings:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT user_id, confidence_threshold, preferred_classifier, auto_train_on_feedback, updated_at
                FROM user_settings
                WHERE user_id = ?
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if row is not None:
                return UserSettings(
                    user_id=row[0],
                    confidence_threshold=float(row[1]),
                    preferred_classifier=row[2],
                    auto_train_on_feedback=bool(row[3]),
                    updated_at=row[4],
                )
        return UserSettings(user_id=user_id)

    def update(self, user_id: str, **fields: Any) -> UserSettings:
        current = self.get_or_default(user_id)
        valid_fields = {
            "confidence_threshold",
            "preferred_classifier",
            "auto_train_on_feedback",
        }
        for k, v in fields.items():
            if k in valid_fields:
                if k == "confidence_threshold":
                    v = float(v)
                elif k == "auto_train_on_feedback":
                    v = bool(v)
                elif k == "preferred_classifier":
                    v = str(v)
                setattr(current, k, v)
        now = datetime.now(timezone.utc).isoformat()
        current.updated_at = now

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_settings (
                    user_id, confidence_threshold, preferred_classifier, auto_train_on_feedback, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    current.user_id,
                    current.confidence_threshold,
                    current.preferred_classifier,
                    int(current.auto_train_on_feedback),
                    current.updated_at,
                ),
            )
            conn.commit()
        return current

    def list_all(self) -> list[UserSettings]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT user_id, confidence_threshold, preferred_classifier, auto_train_on_feedback, updated_at
                FROM user_settings
                ORDER BY user_id
                """
            )
            return [
                UserSettings(
                    user_id=row[0],
                    confidence_threshold=float(row[1]),
                    preferred_classifier=row[2],
                    auto_train_on_feedback=bool(row[3]),
                    updated_at=row[4],
                )
                for row in cursor.fetchall()
            ]
