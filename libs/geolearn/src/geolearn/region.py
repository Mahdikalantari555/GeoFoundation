from __future__ import annotations

import copy

import numpy as np

from geolearn.classifier import OnlineClassifier


def build_hierarchical_key(
    crop_type: str, region: str, sub_region: str | None = None
) -> str:
    """Build a dotted hierarchical key from crop, region, and optional sub_region."""
    crop_type = crop_type.strip()
    region = region.strip()
    if sub_region is not None and sub_region.strip():
        return f"{crop_type}.{region}.{sub_region.strip()}"
    return f"{crop_type}.{region}"


def parse_hierarchical_key(
    key: str | tuple[str, ...],
) -> tuple[str, str, str | None]:
    """Parse a hierarchical key (dotted string or tuple) into (crop, region, sub_region)."""
    if isinstance(key, str):
        parts = key.split(".")
        if len(parts) == 1:
            raise ValueError(f"Invalid hierarchical key string: {key}")
        crop = parts[0]
        region = parts[1]
        sub_region = ".".join(parts[2:]) if len(parts) > 2 else None
        return crop, region, sub_region
    elif isinstance(key, tuple):
        if len(key) < 2:
            raise ValueError(f"Invalid hierarchical key tuple: {key}")
        crop = key[0]
        region = key[1]
        sub_region = key[2] if len(key) >= 3 else None
        return crop, region, sub_region
    else:
        raise TypeError(f"Key must be str or tuple, got {type(key)}")


def get_parent_key(key: str | tuple[str, ...]) -> str | None:
    """Return the parent dotted key for a sub-region key, or None if no parent exists."""
    crop, region, sub_region = parse_hierarchical_key(key)
    if sub_region is not None:
        return f"{crop}.{region}"
    return None


def transfer_weights(
    parent_classifier: OnlineClassifier,
    child_classifier: OnlineClassifier | None = None,
) -> OnlineClassifier:
    """Initialize a child classifier with parent coef_ and intercept_ weights.

    The child starts with the same coefficients as the parent, but subsequent
    partial_fit() calls update only the child weights independently.
    """
    if child_classifier is None:
        child_classifier = OnlineClassifier(
            default_classes=parent_classifier.classes_,
            choice=parent_classifier.choice,
            random_state=parent_classifier.random_state,
        )

    if parent_classifier.is_fitted:
        child_classifier.clf = copy.deepcopy(parent_classifier.clf)
        if hasattr(parent_classifier.clf, "coef_"):
            child_classifier.clf.coef_ = np.copy(parent_classifier.clf.coef_)
        if hasattr(parent_classifier.clf, "intercept_"):
            child_classifier.clf.intercept_ = np.copy(
                parent_classifier.clf.intercept_
            )
        if hasattr(parent_classifier.clf, "classes_"):
            child_classifier.clf.classes_ = np.copy(
                parent_classifier.clf.classes_
            )
        child_classifier.classes_ = (
            list(parent_classifier.classes_)
            if parent_classifier.classes_ is not None
            else None
        )
        child_classifier.is_fitted = True
        child_classifier.n_samples_ = 0

    return child_classifier
