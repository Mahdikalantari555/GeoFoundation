"""Edge deployment runtime module for GeoLearn classifiers."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from geolearn.exceptions import ClassifierNotTrainedError


def export_edge_model(
    classifier: Any,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Export an OnlineClassifier to a standalone bundle for edge/CPU inference.

    Produces:
    - classifier.json: Metadata and base64-encoded weights and intercept
    - weights.npy: Raw flattened / 2D numpy weight matrix
    - intercept.npy: Raw numpy bias array
    - manifest.txt: Human-readable summary
    - README.md: Documentation for the bundle
    """
    if not getattr(classifier, "is_fitted", False):
        raise ClassifierNotTrainedError(
            "Classifier must be fitted before export_for_edge"
        )

    clf = getattr(classifier, "clf", None)
    if clf is None or not hasattr(clf, "coef_") or not hasattr(clf, "intercept_"):
        raise ClassifierNotTrainedError("Classifier weights not found")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    weights = np.asarray(clf.coef_, dtype=np.float32)
    intercept = np.asarray(clf.intercept_, dtype=np.float32)

    raw_classes = getattr(classifier, "classes_", None) or []
    classes = [
        int(c) if isinstance(c, (int, np.integer)) or (isinstance(c, str) and c.isdigit()) else str(c)
        for c in raw_classes
    ]

    if hasattr(clf, "n_features_in_"):
        n_features = int(clf.n_features_in_)
    else:
        n_features = int(weights.shape[1]) if weights.ndim > 1 else int(weights.shape[0])

    n_samples = int(getattr(classifier, "n_samples_", 0))
    exported_at = datetime.now(timezone.utc).isoformat()

    weights_b64 = base64.b64encode(weights.tobytes()).decode("ascii")
    intercept_b64 = base64.b64encode(intercept.tobytes()).decode("ascii")

    classifier_meta = {
        "classes": [str(c) for c in classes],
        "n_classes": len(classes),
        "n_features": n_features,
        "n_samples": n_samples,
        "exported_at": exported_at,
        "weights": weights_b64,
        "intercept": intercept_b64,
        "weights_shape": list(weights.shape),
        "intercept_shape": list(intercept.shape),
    }

    with open(output_path / "classifier.json", "w", encoding="utf-8") as f:
        json.dump(classifier_meta, f, indent=2)

    np.save(output_path / "weights.npy", weights)
    np.save(output_path / "intercept.npy", intercept)

    manifest_lines = [
        "GeoLearn Edge Model Manifest",
        "============================",
        "Version: 1.0",
        f"Export Date: {exported_at}",
        f"Classes: {[str(c) for c in classes]}",
        f"Number of Classes: {len(classes)}",
        f"Number of Features: {n_features}",
        f"Number of Samples: {n_samples}",
        f"Weight Shape: {list(weights.shape)}",
        f"Intercept Shape: {list(intercept.shape)}",
    ]
    (output_path / "manifest.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    readme_text = (
        "# GeoLearn Edge Model Bundle\n\n"
        "This bundle contains exported weights and metadata for standalone edge inference.\n"
        "Inference requires only NumPy (zero scikit-learn runtime dependency).\n\n"
        "Files:\n"
        "- classifier.json: Metadata and base64-encoded weights/intercept\n"
        "- weights.npy: Raw numpy weights array\n"
        "- intercept.npy: Raw numpy bias array\n"
        "- manifest.txt: Human-readable model information\n"
    )
    (output_path / "README.md").write_text(readme_text, encoding="utf-8")

    return {
        "status": "exported",
        "output_dir": str(output_path),
        "files": [
            "classifier.json",
            "weights.npy",
            "intercept.npy",
            "manifest.txt",
            "README.md",
        ],
        "n_classes": len(classes),
        "n_features": n_features,
        "n_samples": n_samples,
        "exported_at": exported_at,
    }


class EdgeLoader:
    """Zero-dependency runtime predictor that executes inference using only NumPy."""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        json_path = self.output_dir / "classifier.json"
        if not json_path.exists():
            raise FileNotFoundError(f"classifier.json not found in {self.output_dir}")

        with open(json_path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        raw_classes = data.get("classes", [])
        self.classes: list[int] = [
            int(c) if (isinstance(c, int) or (isinstance(c, str) and c.isdigit())) else c
            for c in raw_classes
        ]
        self.n_classes: int = int(data.get("n_classes", len(self.classes)))
        self.n_features: int = int(data.get("n_features", 0))
        self.n_samples: int = int(data.get("n_samples", 0))
        self.exported_at: str = str(data.get("exported_at", ""))

        weights_file = self.output_dir / "weights.npy"
        intercept_file = self.output_dir / "intercept.npy"

        if weights_file.exists():
            self._weights: np.ndarray = np.load(weights_file)
        elif data.get("weights"):
            raw_w = np.frombuffer(base64.b64decode(data["weights"]), dtype=np.float32)
            n_rows = 1 if self.n_classes == 2 else self.n_classes
            self._weights = raw_w.reshape((n_rows, self.n_features))
        else:
            raise ValueError("No weights found in edge bundle")

        if intercept_file.exists():
            self._intercept: np.ndarray = np.load(intercept_file)
        elif data.get("intercept"):
            self._intercept = np.frombuffer(
                base64.b64decode(data["intercept"]), dtype=np.float32
            )
        else:
            raise ValueError("No intercept found in edge bundle")

        manifest_file = self.output_dir / "manifest.txt"
        self.manifest: str = (
            manifest_file.read_text(encoding="utf-8") if manifest_file.exists() else ""
        )

    @property
    def weights(self) -> np.ndarray:
        return self._weights

    @property
    def intercept(self) -> np.ndarray:
        return self._intercept

    def predict(self, X: Any) -> list[int]:
        """Predict class labels using matrix multiplication and argmax/threshold."""
        X_arr = np.asarray(X, dtype=np.float32)
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(1, -1)

        if self._weights.shape[0] == 1 and self.n_classes == 2:
            logits = X_arr @ self._weights.T + self._intercept
            preds = [self.classes[1 if val > 0 else 0] for val in logits.flatten()]
            return preds
        else:
            logits = X_arr @ self._weights.T + self._intercept
            indices = np.argmax(logits, axis=1)
            return [self.classes[i] for i in indices]

    def predict_proba(self, X: Any) -> list[list[float]]:
        """Predict class probabilities using sigmoid / normalized sigmoid."""
        X_arr = np.asarray(X, dtype=np.float32)
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(1, -1)

        if self._weights.shape[0] == 1 and self.n_classes == 2:
            logits = X_arr @ self._weights.T + self._intercept
            p1 = 1.0 / (1.0 + np.exp(-np.clip(logits, -88.0, 88.0)))
            p0 = 1.0 - p1
            probas = np.hstack([p0, p1])
            return probas.tolist()  # type: ignore[no-any-return]
        else:
            logits = X_arr @ self._weights.T + self._intercept
            sig = 1.0 / (1.0 + np.exp(-np.clip(logits, -88.0, 88.0)))
            denom = np.sum(sig, axis=1, keepdims=True)
            denom = np.where(denom == 0, 1.0, denom)
            probas = sig / denom
            return probas.tolist()  # type: ignore[no-any-return]
