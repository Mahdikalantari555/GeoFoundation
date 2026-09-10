"""Model versioning and rollback recovery for GeoLearn classifiers."""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from geolearn.classifier import OnlineClassifier

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    key: tuple[str, ...]
    version: int
    timestamp: str  # ISO 8601
    n_samples: int
    sha256: str  # of the pkl file


class ModelVersionManager:
    """Manages model versions, rollbacks, and automatic garbage collection."""

    def __init__(self, workspace_dir: str | Path) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        if (self.workspace_dir / "geolearn" / "models").exists():
            self.models_dir = self.workspace_dir / "geolearn" / "models"
        elif (self.workspace_dir / "models").exists() or self.workspace_dir.name == "geolearn":
            self.models_dir = self.workspace_dir / "models"
        else:
            self.models_dir = self.workspace_dir / "geolearn" / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)

        if (self.workspace_dir / "geolearn.db").exists():
            self.db_path = self.workspace_dir / "geolearn.db"
        elif (self.workspace_dir / "geolearn" / "geolearn.db").exists():
            self.db_path = self.workspace_dir / "geolearn" / "geolearn.db"
        elif (self.workspace_dir.parent / "geolearn.db").exists():
            self.db_path = self.workspace_dir.parent / "geolearn.db"
        else:
            self.db_path = self.workspace_dir / "geolearn.db"

        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS classifier_state (
                    key_crop TEXT NOT NULL,
                    key_region TEXT NOT NULL,
                    sub_region TEXT,
                    version TEXT NOT NULL,
                    fitted_at TEXT NOT NULL,
                    n_samples INTEGER NOT NULL
                )
                """
            )
            cursor = conn.execute("PRAGMA table_info(classifier_state)")
            cols = [row[1] for row in cursor.fetchall()]
            if "sub_region" not in cols:
                conn.execute("ALTER TABLE classifier_state ADD COLUMN sub_region TEXT NULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS model_versions (
                    key_crop TEXT NOT NULL,
                    key_region TEXT NOT NULL,
                    key TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    n_samples INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    PRIMARY KEY (key_crop, key_region, version)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rollback_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    key_crop TEXT NOT NULL,
                    key_region TEXT NOT NULL,
                    from_version INTEGER,
                    to_version INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    reason TEXT
                )
                """
            )
            conn.commit()

    @staticmethod
    def _normalize_key(key: tuple[str, ...] | Sequence[str] | str) -> tuple[str, ...]:
        if isinstance(key, (tuple, list)):
            if len(key) >= 3:
                return (str(key[0]), str(key[1]), str(key[2]))
            return (str(key[0]), str(key[1]))
        if isinstance(key, str):
            if "." in key:
                parts = key.split(".")
                if len(parts) >= 3:
                    return (parts[0], parts[1], parts[2])
                elif len(parts) == 2:
                    return (parts[0], parts[1])
            if "__" in key:
                parts = key.split("__")
                if len(parts) >= 3:
                    return (parts[0], parts[1], parts[2])
                elif len(parts) == 2:
                    return (parts[0], parts[1])
            return (key, "global")
        raise TypeError(f"Unsupported key format: {type(key)}")

    def _key_dir(self, key: tuple[str, ...]) -> Path:
        if len(key) >= 3:
            return self.models_dir / f"{key[0]}__{key[1]}__{key[2]}"
        return self.models_dir / f"{key[0]}__{key[1]}"

    def save_version(
        self,
        key: tuple[str, str] | Sequence[str] | str,
        classifier: OnlineClassifier,
        n_samples: int = 0,
    ) -> ModelVersion:
        """Save a new versioned checkpoint for a classifier key."""
        norm_key = self._normalize_key(key)
        crop = norm_key[0]
        region = norm_key[1]
        sub_region = norm_key[2] if len(norm_key) >= 3 else None
        key_str = f"{crop}__{region}__{sub_region}" if sub_region else f"{crop}__{region}"
        key_dir = self._key_dir(norm_key)
        key_dir.mkdir(parents=True, exist_ok=True)

        existing_versions = self.list_versions(norm_key)
        max_v = max([v.version for v in existing_versions], default=0)
        next_v = max_v + 1

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        filename = f"{next_v:04d}_{timestamp}.pkl"
        file_path = key_dir / filename

        classifier.save(file_path)
        sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()

        # Update the active classifier.pkl link/copy
        shutil.copy2(file_path, key_dir / "classifier.pkl")

        sub_region = norm_key[2] if len(norm_key) >= 3 else None
        key_str = f"{crop}__{region}__{sub_region}" if sub_region else f"{crop}__{region}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO model_versions
                (key_crop, key_region, key, version, timestamp, n_samples, sha256, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (crop, region, key_str, next_v, timestamp, n_samples, sha256, str(file_path)),
            )
            conn.execute(
                """
                DELETE FROM classifier_state
                WHERE key_crop = ? AND key_region = ? AND (sub_region = ? OR (sub_region IS NULL AND ? IS NULL))
                """,
                (crop, region, sub_region, sub_region),
            )
            conn.execute(
                """
                INSERT INTO classifier_state
                (key_crop, key_region, sub_region, version, fitted_at, n_samples)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (crop, region, sub_region, sha256, timestamp, n_samples),
            )
            conn.commit()

        # Enforce garbage collection: keep only last 10 versions
        self.garbage_collect(norm_key, keep=10)

        return ModelVersion(
            key=norm_key,
            version=next_v,
            timestamp=timestamp,
            n_samples=n_samples,
            sha256=sha256,
        )

    def list_versions(
        self,
        key: tuple[str, str] | Sequence[str] | str | None = None,
    ) -> list[ModelVersion]:
        """List model versions sorted descending by version."""
        self._sync_disk_versions()
        with sqlite3.connect(self.db_path) as conn:
            if key is not None:
                norm_key = self._normalize_key(key)
                cursor = conn.execute(
                    """
                    SELECT key_crop, key_region, version, timestamp, n_samples, sha256
                    FROM model_versions
                    WHERE key_crop = ? AND key_region = ?
                    ORDER BY version DESC
                    """,
                    (norm_key[0], norm_key[1]),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT key_crop, key_region, version, timestamp, n_samples, sha256
                    FROM model_versions
                    ORDER BY version DESC, timestamp DESC
                    """
                )
            rows = cursor.fetchall()

        return [
            ModelVersion(
                key=(r[0], r[1]),
                version=int(r[2]),
                timestamp=str(r[3]),
                n_samples=int(r[4]),
                sha256=str(r[5]),
            )
            for r in rows
        ]

    def rollback_to(
        self,
        key: tuple[str, str] | Sequence[str] | str,
        version: int,
        reason: str = "",
    ) -> bool:
        """Rollback active classifier to a previous version."""
        norm_key = self._normalize_key(key)
        crop = norm_key[0]
        region = norm_key[1]
        sub_region = norm_key[2] if len(norm_key) >= 3 else None
        key_str = f"{crop}__{region}__{sub_region}" if sub_region else f"{crop}__{region}"
        key_dir = self._key_dir(norm_key)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT version, timestamp, n_samples, sha256, file_path
                FROM model_versions
                WHERE key_crop = ? AND key_region = ? AND version = ?
                """,
                (crop, region, version),
            )
            row = cursor.fetchone()

        if row is None:
            # Check if file exists on disk
            matches = sorted(key_dir.glob(f"{version:04d}_*.pkl"))
            if not matches:
                logger.warning(
                    "Rollback target version %d for key %s not found",
                    version,
                    norm_key,
                )
                return False
            target_path = matches[0]
            sha256 = hashlib.sha256(target_path.read_bytes()).hexdigest()
            target_timestamp = datetime.now(timezone.utc).isoformat()
            target_n_samples = 0
        else:
            target_path = Path(row[4])
            if not target_path.exists():
                logger.warning(
                    "Rollback target file %s does not exist on disk",
                    target_path,
                )
                return False
            sha256 = str(row[3])
            target_timestamp = str(row[1])
            target_n_samples = int(row[2])

        # Validate that model can be loaded
        try:
            OnlineClassifier.load(target_path)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to load rollback model: %s", e)
            return False

        # Overwrite active classifier.pkl
        active_pkl = key_dir / "classifier.pkl"
        from_version: int | None = None
        if active_pkl.exists():
            active_sha = hashlib.sha256(active_pkl.read_bytes()).hexdigest()
            for v in self.list_versions(norm_key):
                if v.sha256 == active_sha:
                    from_version = v.version
                    break

        shutil.copy2(target_path, active_pkl)

        now = datetime.now(timezone.utc).isoformat()
        reason_text = reason or f"Rollback to version {version}"

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO classifier_state
                (key_crop, key_region, version, fitted_at, n_samples)
                VALUES (?, ?, ?, ?, ?)
                """,
                (crop, region, sha256, target_timestamp, target_n_samples),
            )
            conn.execute(
                """
                INSERT INTO rollback_history
                (key, key_crop, key_region, from_version, to_version, timestamp, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (key_str, crop, region, from_version, version, now, reason_text),
            )
            conn.commit()

        logger.info(
            "Rolled back %s from version %s to version %d",
            norm_key,
            from_version,
            version,
        )
        return True

    def garbage_collect(
        self,
        key: tuple[str, str] | Sequence[str] | str,
        keep: int = 10,
    ) -> list[int]:
        """Keep only the latest `keep` versions per key, deleting older files and DB rows."""
        norm_key = self._normalize_key(key)
        crop = norm_key[0]
        region = norm_key[1]
        versions = self.list_versions(norm_key)

        if len(versions) <= keep:
            return []

        to_remove = versions[keep:]
        removed_versions: list[int] = []

        with sqlite3.connect(self.db_path) as conn:
            for v in to_remove:
                cursor = conn.execute(
                    """
                    SELECT file_path FROM model_versions
                    WHERE key_crop = ? AND key_region = ? AND version = ?
                    """,
                    (crop, region, v.version),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    p = Path(row[0])
                    p.unlink(missing_ok=True)
                else:
                    key_dir = self._key_dir(norm_key)
                    for f in key_dir.glob(f"{v.version:04d}_*.pkl"):
                        f.unlink(missing_ok=True)

                conn.execute(
                    """
                    DELETE FROM model_versions
                    WHERE key_crop = ? AND key_region = ? AND version = ?
                    """,
                    (crop, region, v.version),
                )
                removed_versions.append(v.version)

            conn.commit()

        return removed_versions

    def _sync_disk_versions(self) -> None:
        """Scan models_dir to ensure any disk versions are registered in DB."""
        if not self.models_dir.exists():
            return

        version_regex = re.compile(r"^(\d{4})_(.+)\.pkl$")
        with sqlite3.connect(self.db_path) as conn:
            for key_dir in self.models_dir.iterdir():
                if not key_dir.is_dir() or "__" not in key_dir.name:
                    continue
                crop, region = key_dir.name.split("__", 1)
                for pkl_file in key_dir.glob("*.pkl"):
                    if pkl_file.name == "classifier.pkl":
                        continue
                    m = version_regex.match(pkl_file.name)
                    if not m:
                        continue
                    version = int(m.group(1))
                    ts = m.group(2)
                    cur = conn.execute(
                        """
                        SELECT 1 FROM model_versions
                        WHERE key_crop = ? AND key_region = ? AND version = ?
                        """,
                        (crop, region, version),
                    )
                    if cur.fetchone() is None:
                        sha256 = hashlib.sha256(pkl_file.read_bytes()).hexdigest()
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO model_versions
                            (key_crop, key_region, key, version, timestamp, n_samples, sha256, file_path)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (crop, region, key_dir.name, version, ts, 0, sha256, str(pkl_file)),
                        )
            conn.commit()
