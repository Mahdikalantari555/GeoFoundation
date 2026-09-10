from __future__ import annotations

import hashlib
import inspect
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from geolearn.cache import EmbeddingCache
from geolearn.classifier import OnlineClassifier
from geolearn.confidence import ConfidenceModel
from geolearn.frozen_adapter import FrozenEmbeddingAdapter
from geolearn.models import PredictionResult
from geolearn.profiles import ProfileStore
from geolearn.region import (
    build_hierarchical_key,
    get_parent_key,
    parse_hierarchical_key,
    transfer_weights,
)
from geolearn.user_settings import UserSettingsStore
from geolearn.versioning import ModelVersion, ModelVersionManager


class ClassifierStore:
    def __init__(
        self,
        workspace_dir: str | Path,
        scheduler: Any = None,
    ) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.workspace_dir / "geolearn.db"
        self.models_dir = self.workspace_dir / "geolearn" / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.profile_store = ProfileStore(self.workspace_dir)
        self.user_settings_store = UserSettingsStore(self.workspace_dir)
        self.cache = EmbeddingCache(self.workspace_dir)
        self.scheduler = scheduler
        self.version_manager = ModelVersionManager(self.workspace_dir)
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
            cols_info = cursor.fetchall()
            columns = [row[1] for row in cols_info]
            if "sub_region" not in columns:
                conn.execute("ALTER TABLE classifier_state ADD COLUMN sub_region TEXT NULL")
                cursor = conn.execute("PRAGMA table_info(classifier_state)")
                cols_info = cursor.fetchall()

            pk_cols = [row[1] for row in cols_info if row[5] > 0]
            if pk_cols == ["key_crop", "key_region"]:
                conn.execute(
                    """
                    CREATE TABLE classifier_state_v2 (
                        key_crop TEXT NOT NULL,
                        key_region TEXT NOT NULL,
                        sub_region TEXT,
                        version TEXT NOT NULL,
                        fitted_at TEXT NOT NULL,
                        n_samples INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO classifier_state_v2 (key_crop, key_region, sub_region, version, fitted_at, n_samples)
                    SELECT key_crop, key_region, sub_region, version, fitted_at, n_samples FROM classifier_state
                    """
                )
                conn.execute("DROP TABLE classifier_state")
                conn.execute("ALTER TABLE classifier_state_v2 RENAME TO classifier_state")
            conn.commit()

    def _model_path(self, key: tuple[str, ...] | str) -> Path:
        crop, region, sub_region = parse_hierarchical_key(key)
        if sub_region:
            return self.models_dir / f"{crop}__{region}__{sub_region}" / "classifier.pkl"
        return self.models_dir / f"{crop}__{region}" / "classifier.pkl"

    def get_or_create_key(
        self, crop_type: str, region: str, sub_region: str | None = None
    ) -> str:
        key = build_hierarchical_key(crop_type, region, sub_region)
        if sub_region is not None:
            sub_path = self._model_path(key)
            if not sub_path.exists():
                parent_key = build_hierarchical_key(crop_type, region)
                parent_path = self._model_path(parent_key)
                if parent_path.exists():
                    parent_clf = OnlineClassifier.load(parent_path)
                    if parent_clf.is_fitted:
                        child_clf = transfer_weights(parent_clf)
                        self.save_classifier(key, child_clf, n_samples=0)
        return key

    def select_key(
        self, user_id: str, region: str, crop_type: str = "unknown"
    ) -> str:
        profile = self.profile_store.get(user_id, region)
        if profile is None and user_id == "anonymous":
            profile = self.profile_store.get_or_create("anonymous", region)
        if profile is not None:
            resolved_crop = crop_type if crop_type != "unknown" else profile.crop_type
            if profile.preferred_classifier and profile.preferred_classifier != "sgd":
                return f"{resolved_crop}.{region}.{profile.preferred_classifier}"
            return f"{resolved_crop}.{region}"
        if crop_type == "unknown" and region == "global":
            return "unknown.global"
        return f"{crop_type}.{region}"

    def get_classifier(
        self, key: tuple[str, ...] | str = ("unknown", "global")
    ) -> OnlineClassifier:
        path = self._model_path(key)
        if path.exists():
            return OnlineClassifier.load(path)

        parent_key = get_parent_key(key)
        if parent_key is not None:
            parent_path = self._model_path(parent_key)
            if parent_path.exists():
                parent_clf = OnlineClassifier.load(parent_path)
                if parent_clf.is_fitted:
                    child_clf = transfer_weights(parent_clf)
                    self.save_classifier(key, child_clf, n_samples=0)
                    return child_clf

        fallback_path = self._model_path(("unknown", "global"))
        if fallback_path.exists():
            return OnlineClassifier.load(fallback_path)
        return OnlineClassifier()

    def save_classifier(
        self,
        key: tuple[str, ...] | str,
        classifier: OnlineClassifier,
        n_samples: int = 0,
    ) -> str:
        path = self._model_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        classifier.save(path)

        with open(path, "rb") as f:
            data = f.read()
            version = hashlib.sha256(data).hexdigest()

        now = datetime.now(timezone.utc).isoformat()
        crop, region, sub_region = parse_hierarchical_key(key)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                DELETE FROM classifier_state
                WHERE key_crop = ? AND key_region = ? AND (sub_region = ? OR (sub_region IS NULL AND ? IS NULL))
                """,
                (crop, region, sub_region, sub_region),
            )
            conn.execute(
                """
                INSERT INTO classifier_state (key_crop, key_region, sub_region, version, fitted_at, n_samples)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (crop, region, sub_region, version, now, n_samples),
            )
            conn.commit()
        # Track version with ModelVersionManager and prune old versions
        self.version_manager.save_version(key, classifier, n_samples=n_samples)
        return version

    def list_versions(
        self, key: tuple[str, ...] | str | None = None
    ) -> list[ModelVersion]:
        return self.version_manager.list_versions(key)

    def rollback_to(
        self, key: tuple[str, ...] | str, version: int, reason: str = ""
    ) -> bool:
        return self.version_manager.rollback_to(key, version, reason=reason)

    def get_n_samples(self, key: tuple[str, ...] | str) -> int:
        crop, region, sub_region = parse_hierarchical_key(key)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                SELECT n_samples FROM classifier_state
                WHERE key_crop = ? AND key_region = ? AND (sub_region = ? OR (sub_region IS NULL AND ? IS NULL))
                """,
                (crop, region, sub_region, sub_region),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def predict_for_key(
        self,
        embeddings: Any,
        key: tuple[str, ...] | str = ("unknown", "global"),
        confidence_model: ConfidenceModel | None = None,
        user_id: str | None = None,
    ) -> PredictionResult:
        if user_id is not None:
            user_settings = self.user_settings_store.get_or_default(user_id)
            if confidence_model is not None:
                conf_model = confidence_model
                conf_model.threshold = user_settings.confidence_threshold
            else:
                conf_model = ConfidenceModel(threshold=user_settings.confidence_threshold)
        else:
            conf_model = confidence_model or ConfidenceModel()

        n_samples = self.get_n_samples(key)
        clf = self.get_classifier(key)

        if n_samples < 30:
            adapter = FrozenEmbeddingAdapter(
                cache=self.cache,
                k=5,
                classifier=clf,
                n_training_samples=n_samples,
            )
            res = adapter.predict(
                embeddings,
                key=key if isinstance(key, tuple) and len(key) == 2 else ("unknown", "global"),
                confidence_model=conf_model,
            )
            path = self._model_path(key)
            if not path.exists():
                path = self._model_path(("unknown", "global"))
            if path.exists():
                with open(path, "rb") as f:
                    res.model_version = hashlib.sha256(f.read()).hexdigest()
            res.key = key
            return res

        X = np.asarray(embeddings, dtype=np.float32)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        sig = inspect.signature(clf.predict)
        if "user_id" in sig.parameters:
            labels = [int(l) for l in clf.predict(X, user_id=user_id)]
        else:
            labels = [int(l) for l in clf.predict(X)]

        probas = clf.predict_proba(X)
        confidences, abstain = conf_model.evaluate(probas)

        path = self._model_path(key)
        if not path.exists():
            path = self._model_path(("unknown", "global"))

        if path.exists():
            with open(path, "rb") as f:
                version = hashlib.sha256(f.read()).hexdigest()
        else:
            version = "unversioned"

        return PredictionResult(
            labels=labels,
            confidence=confidences,
            abstain=abstain,
            key=key,
            n_samples=len(labels),
            model_version=version,
            source="classifier",
        )

    def predict(
        self,
        embeddings: Any,
        key: tuple[str, ...] | str = ("unknown", "global"),
        confidence_model: ConfidenceModel | None = None,
        user_id: str | None = None,
    ) -> PredictionResult:
        return self.predict_for_key(
            embeddings,
            key=key,
            confidence_model=confidence_model,
            user_id=user_id,
        )

    def partial_fit(
        self,
        key: tuple[str, ...] | str,
        embeddings: Any,
        labels: Any,
        classes: list[int] | None = None,
    ) -> None:
        clf = self.get_classifier(key)
        X_arr = np.asarray(embeddings, dtype=np.float32)
        y_arr = np.asarray(labels, dtype=np.int64)

        if self.scheduler is not None:
            for x, y in zip(X_arr, y_arr):
                self.scheduler.add(x, int(y))
            trained = self.scheduler.maybe_train(clf)
            if trained:
                trained_count = getattr(self.scheduler, "last_trained_count", len(X_arr))
                n_samples = self.get_n_samples(key) + trained_count
                self.save_classifier(key, clf, n_samples=n_samples)
        else:
            clf.partial_fit(X_arr, y_arr, classes=classes)
            n_samples = self.get_n_samples(key) + len(X_arr)
            self.save_classifier(key, clf, n_samples=n_samples)

