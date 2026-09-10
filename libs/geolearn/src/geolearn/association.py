from __future__ import annotations

import hashlib
from typing import Any

import numpy as np


def compute_embedding_hash(embedding: Any) -> str:
    """Compute sha256 hex digest of serialized float32 embedding bytes."""
    if isinstance(embedding, str):
        return embedding
    arr = np.asarray(embedding, dtype=np.float32)
    return hashlib.sha256(arr.tobytes()).hexdigest()


class AssociationMap:
    """Maintains an incremental (embedding_hash, label) -> score mapping with exponential decay."""

    def __init__(self, half_life_days: float = 90.0) -> None:
        if half_life_days <= 0:
            raise ValueError(f"half_life_days must be positive, got {half_life_days}")
        self.half_life_days = float(half_life_days)
        self.scores: dict[tuple[str, int], float] = {}

    def decay(self, dt_days: float) -> None:
        """Apply exponential decay to all scores and prune those below 0.01."""
        if dt_days <= 0:
            return
        factor = 2.0 ** (-dt_days / self.half_life_days)
        to_prune: list[tuple[str, int]] = []
        for k, v in self.scores.items():
            new_v = v * factor
            if new_v < 0.01:
                to_prune.append(k)
            else:
                self.scores[k] = new_v
        for k in to_prune:
            del self.scores[k]

    def update(
        self,
        embedding_or_hash: Any,
        label: int,
        dt_days: float = 0.0,
    ) -> float:
        """Update association map with a new labeled sample and optional decay interval."""
        if dt_days > 0:
            self.decay(dt_days)
        h = compute_embedding_hash(embedding_or_hash)
        pair = (h, int(label))
        new_score = self.scores.get(pair, 0.0) + 1.0
        self.scores[pair] = new_score
        return new_score

    def scores_for(self, embedding_or_hash: Any) -> dict[int, float]:
        """Return current score map for a given embedding or hash."""
        h = compute_embedding_hash(embedding_or_hash)
        result: dict[int, float] = {}
        for (k_hash, label), score in self.scores.items():
            if k_hash == h:
                result[label] = score
        return result

    def blend(
        self,
        classifier_proba: Any,
        embedding: Any,
        key: tuple[str, str] | None = None,
        classes: list[int] | None = None,
    ) -> np.ndarray:
        """Combine classifier probability with association-map vote (50/50 blend)."""
        proba_arr = np.asarray(classifier_proba, dtype=np.float64)
        single_row = proba_arr.ndim == 1

        if single_row:
            row = proba_arr
            scores = self.scores_for(embedding)
            if not scores or sum(scores.values()) == 0:
                return proba_arr

            class_list = classes if classes is not None else list(range(len(row)))
            total_score = sum(scores.values())
            assoc_dist = np.array(
                [scores.get(c, 0.0) / total_score for c in class_list],
                dtype=np.float64,
            )

            if np.sum(assoc_dist) == 0:
                return proba_arr

            blended = 0.5 * row + 0.5 * assoc_dist
            s = np.sum(blended)
            if s > 0:
                blended = blended / s
            return blended

        # 2D array case (N, n_classes)
        result = np.copy(proba_arr)
        emb_arr = np.asarray(embedding, dtype=np.float32)
        for i in range(len(result)):
            emb_i = emb_arr[i] if emb_arr.ndim > 1 else emb_arr
            result[i] = self.blend(
                result[i],
                emb_i,
                key=key,
                classes=classes,
            )
        return result
