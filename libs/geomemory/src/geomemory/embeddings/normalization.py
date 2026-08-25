"""Vector normalization utilities."""

from __future__ import annotations

import numpy as np


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize a (N, D) array along the last axis.

    Zero vectors are left as-is (norm 0 → unchanged) to avoid NaN.
    """
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    safe = np.where(norms == 0, 1.0, norms)
    return arr / safe


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return the cosine similarity between two (N, D) arrays (row-wise)."""
    a_n = l2_normalize(a)
    b_n = l2_normalize(b)
    return np.sum(a_n * b_n, axis=1)
