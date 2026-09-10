from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from geolearn.cache import EmbeddingCache
from geolearn.calibration import compute_final_confidence, prediction_entropy
from geolearn.classifier import OnlineClassifier
from geolearn.confidence import ConfidenceModel
from geolearn.models import PredictionResult


class FrozenEmbeddingAdapter:
    """k-NN fallback over cached foundation model embeddings when training data is scarce."""

    def __init__(
        self,
        cache: EmbeddingCache,
        k: int = 5,
        classifier: OnlineClassifier | None = None,
        n_training_samples: int = 0,
        threshold: int = 30,
        labels: dict[str, int] | None = None,
    ) -> None:
        self.cache = cache
        self.k = int(k)
        self.classifier = classifier
        self.n_training_samples = int(n_training_samples)
        self.threshold = int(threshold)
        self.labels: dict[str, int] = dict(labels) if labels else {}

    def register_label(self, asset_id: str, label: int) -> None:
        """Register ground truth label for an asset."""
        self.labels[asset_id] = int(label)

    def set_labels(self, labels: dict[str, int]) -> None:
        """Batch set ground truth labels."""
        for k, v in labels.items():
            self.labels[k] = int(v)

    def _get_label(self, asset_id: str) -> int | None:
        if asset_id in self.labels:
            return self.labels[asset_id]
        if hasattr(self.cache, "get_label"):
            return self.cache.get_label(asset_id)
        return None

    def predict(
        self,
        embedding: Any,
        key: tuple[str, str] = ("unknown", "global"),
        classifier: OnlineClassifier | None = None,
        n_training_samples: int | None = None,
        confidence_model: ConfidenceModel | None = None,
    ) -> PredictionResult:
        n_samples = (
            n_training_samples
            if n_training_samples is not None
            else self.n_training_samples
        )
        clf = classifier or self.classifier
        conf_model = confidence_model or ConfidenceModel()

        # When n_training_samples >= 30, delegate to online classifier
        if n_samples >= self.threshold and clf is not None and clf.is_fitted:
            X = np.asarray(embedding, dtype=np.float32)
            if X.ndim == 1:
                X = X.reshape(1, -1)

            labels = [int(lbl) for lbl in clf.predict(X)]
            probas = clf.predict_proba(X)
            confidences, abstain = conf_model.evaluate(probas)

            return PredictionResult(
                labels=labels,
                confidence=confidences,
                abstain=abstain,
                key=key,
                n_samples=len(labels),
                model_version=hashlib.sha256(b"classifier").hexdigest(),
                source="classifier",
            )

        # Fallback k-NN over cached embeddings
        X = np.asarray(embedding, dtype=np.float32)
        single_input = X.ndim == 1
        if single_input:
            X = X.reshape(1, -1)

        pred_labels: list[int] = []
        pred_confs: list[float] = []
        any_abstain = False

        for row in X:
            # Query candidate neighbors from cache
            neighbors = self.cache.nn_lookup(row, k=max(self.k * 3, 20))
            labeled: list[tuple[str, float, int]] = []
            for aid, dist in neighbors:
                lbl = self._get_label(aid)
                if lbl is not None:
                    labeled.append((aid, dist, lbl))

            if not labeled:
                # If no labeled neighbors found in cache, fallback to classifier if fitted
                if clf is not None and clf.is_fitted:
                    sub_X = row.reshape(1, -1)
                    sub_label = int(clf.predict(sub_X)[0])
                    sub_proba = clf.predict_proba(sub_X)
                    sub_conf, sub_abstain = conf_model.evaluate(sub_proba)
                    pred_labels.append(sub_label)
                    pred_confs.append(sub_conf[0])
                    any_abstain = any_abstain or sub_abstain
                    continue

                pred_labels.append(0)
                pred_confs.append(0.0)
                any_abstain = True
                continue

            top_k = labeled[: self.k]
            weights: dict[int, float] = {}
            for _aid, dist, lbl in top_k:
                w = 1.0 / (dist + 1e-5)
                weights[lbl] = weights.get(lbl, 0.0) + w

            total_w = sum(weights.values())
            best_lbl = max(weights.items(), key=lambda item: item[1])[0]
            win_ratio = float(weights[best_lbl] / total_w)

            # Entropy calculation over class distribution
            prob_dist = np.array([w / total_w for w in weights.values()], dtype=np.float64)
            ent = prediction_entropy(prob_dist)
            final_conf = compute_final_confidence(win_ratio, ent)

            is_abstain = conf_model.is_abstain(final_conf) or ent > conf_model.entropy_threshold

            pred_labels.append(best_lbl)
            pred_confs.append(final_conf)
            any_abstain = any_abstain or is_abstain

        return PredictionResult(
            labels=pred_labels,
            confidence=pred_confs,
            abstain=any_abstain,
            key=key,
            n_samples=len(pred_labels),
            model_version=hashlib.sha256(b"nn_fallback").hexdigest(),
            source="nn_fallback",
        )
