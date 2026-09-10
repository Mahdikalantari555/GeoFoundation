from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.linear_model import PassiveAggressiveClassifier, SGDClassifier

from geolearn.exceptions import ClassifierNotTrainedError


class ClassifierChoice(str, Enum):
    SGD = "sgd"
    PASSIVE_AGGRESSIVE = "passive_aggressive"
    INCREMENTAL_KMEANS = "incremental_kmeans"


class OnlineClassifier:
    def __init__(
        self,
        default_classes: list[int] | None = None,
        random_state: int = 42,
        choice: ClassifierChoice | str = ClassifierChoice.SGD,
        n_clusters: int | None = None,
        association_map: Any = None,
    ) -> None:
        self.choice: ClassifierChoice = (
            ClassifierChoice(choice) if isinstance(choice, str) else choice
        )
        self.random_state: int = random_state
        self.classes_: list[int] | None = (
            list(default_classes) if default_classes is not None else None
        )
        self.is_fitted: bool = False
        self.n_samples_: int = 0
        self._n_clusters_param: int | None = n_clusters
        self.association_map: Any = association_map

        if self.choice == ClassifierChoice.SGD:
            self.clf: Any = SGDClassifier(loss="log_loss", random_state=random_state)
        elif self.choice == ClassifierChoice.PASSIVE_AGGRESSIVE:
            self.clf = PassiveAggressiveClassifier(
                C=1.0, max_iter=1000, tol=1e-3, random_state=random_state
            )
        elif self.choice == ClassifierChoice.INCREMENTAL_KMEANS:
            k = n_clusters
            if k is None:
                k = len(self.classes_) if self.classes_ is not None else 8
            self.clf = MiniBatchKMeans(n_clusters=k, random_state=random_state)
        else:
            raise ValueError(f"Unknown classifier choice: {self.choice}")

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        if "choice" not in self.__dict__:
            self.choice = ClassifierChoice.SGD
        if "n_samples_" not in self.__dict__:
            self.n_samples_ = 0
        if "_n_clusters_param" not in self.__dict__:
            self._n_clusters_param = None
        if "random_state" not in self.__dict__:
            self.random_state = 42
        if "association_map" not in self.__dict__:
            self.association_map = None

    def fit(
        self,
        X: Any,
        y: Any = None,
        classes: list[int] | None = None,
    ) -> OnlineClassifier:
        X_arr = np.asarray(X, dtype=np.float32)

        if self.choice == ClassifierChoice.INCREMENTAL_KMEANS:
            if y is not None:
                y_arr = np.asarray(y, dtype=np.int64)
                if classes is not None:
                    self.classes_ = sorted(set(classes))
                else:
                    self.classes_ = sorted(set(y_arr))
                if self._n_clusters_param is None:
                    self.clf = MiniBatchKMeans(
                        n_clusters=len(self.classes_), random_state=self.random_state
                    )
            else:
                if classes is not None:
                    self.classes_ = sorted(set(classes))
                    if self._n_clusters_param is None:
                        self.clf = MiniBatchKMeans(
                            n_clusters=len(self.classes_), random_state=self.random_state
                        )
                elif self.classes_ is None:
                    self.classes_ = list(range(int(self.clf.n_clusters)))
            self.clf.fit(X_arr)
            self.is_fitted = True
            self.n_samples_ = len(X_arr)
            return self

        if y is None:
            raise ValueError(f"y is required for {self.choice.value}")
        y_arr = np.asarray(y, dtype=np.int64)

        if classes is not None:
            self.classes_ = sorted(set(classes))
        else:
            self.classes_ = sorted(set(y_arr))

        if len(self.classes_) == 1:
            single_cls = self.classes_[0]
            self.classes_ = [0, 1] if single_cls in (0, 1) else sorted({0, single_cls})
            self.clf.partial_fit(
                X_arr, y_arr, classes=np.asarray(self.classes_, dtype=np.int64)
            )
        else:
            self.clf.fit(X_arr, y_arr)
        self.is_fitted = True
        self.n_samples_ = len(X_arr)
        return self

    def partial_fit(
        self,
        X: Any,
        y: Any = None,
        classes: list[int] | None = None,
    ) -> OnlineClassifier:
        X_arr = np.asarray(X, dtype=np.float32)

        if self.choice == ClassifierChoice.INCREMENTAL_KMEANS:
            if not self.is_fitted:
                if y is not None:
                    y_arr = np.asarray(y, dtype=np.int64)
                    if classes is not None:
                        self.classes_ = sorted(set(classes))
                    else:
                        self.classes_ = sorted(set(y_arr))
                    if self._n_clusters_param is None:
                        self.clf = MiniBatchKMeans(
                            n_clusters=len(self.classes_),
                            random_state=self.random_state,
                        )
                else:
                    if classes is not None:
                        self.classes_ = sorted(set(classes))
                        if self._n_clusters_param is None:
                            self.clf = MiniBatchKMeans(
                                n_clusters=len(self.classes_),
                                random_state=self.random_state,
                            )
                    elif self.classes_ is None:
                        self.classes_ = list(range(int(self.clf.n_clusters)))
            self.clf.partial_fit(X_arr)
            self.is_fitted = True
            self.n_samples_ += len(X_arr)
            return self

        if y is None:
            raise ValueError(f"y is required for {self.choice.value}")
        y_arr = np.asarray(y, dtype=np.int64)

        if classes is not None:
            self.classes_ = sorted(set(classes))
        elif not self.is_fitted and self.classes_ is None:
            self.classes_ = sorted(set(y_arr))

        if not self.is_fitted:
            self.clf.partial_fit(
                X_arr, y_arr, classes=np.asarray(self.classes_, dtype=np.int64)
            )
            self.is_fitted = True
        else:
            self.clf.partial_fit(X_arr, y_arr)
        self.n_samples_ += len(X_arr)
        return self

    def predict(
        self,
        X: Any,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> np.ndarray:
        if not self.is_fitted:
            raise ClassifierNotTrainedError("Classifier must be fitted before predict")
        X_arr = np.asarray(X, dtype=np.float32)

        assoc = kwargs.get("association_map") or getattr(self, "association_map", None)
        if assoc is not None and self.classes_ is not None:
            probas = self.predict_proba(X_arr, user_id=user_id, **kwargs)
            best_indices = np.argmax(probas, axis=1)
            return np.asarray([self.classes_[i] for i in best_indices], dtype=np.int64)

        preds = self.clf.predict(X_arr)
        return np.asarray(preds, dtype=np.int64)

    def predict_proba(
        self,
        X: Any,
        key: tuple[str, str] | None = None,
        association_map: Any = None,
        **kwargs: Any,
    ) -> np.ndarray:
        if not self.is_fitted:
            raise ClassifierNotTrainedError(
                "Classifier must be fitted before predict_proba"
            )
        X_arr = np.asarray(X, dtype=np.float32)

        if self.choice == ClassifierChoice.PASSIVE_AGGRESSIVE:
            df = np.asarray(self.clf.decision_function(X_arr))
            if df.ndim == 1 or (df.ndim == 2 and df.shape[1] == 1):
                df_flat = df.ravel()
                p1 = 1.0 / (1.0 + np.exp(-np.clip(df_flat, -500.0, 500.0)))
                p0 = 1.0 - p1
                probas = np.column_stack([p0, p1])
            else:
                shifted = df - np.max(df, axis=1, keepdims=True)
                exp_df = np.exp(np.clip(shifted, -500.0, 500.0))
                probas = exp_df / np.sum(exp_df, axis=1, keepdims=True)
            res = np.asarray(probas, dtype=np.float64)
        elif self.choice == ClassifierChoice.INCREMENTAL_KMEANS:
            distances = np.asarray(self.clf.transform(X_arr), dtype=np.float64)
            inv_dist = 1.0 / np.maximum(distances, 1e-10)
            probas = inv_dist / np.sum(inv_dist, axis=1, keepdims=True)
            res = np.asarray(probas, dtype=np.float64)
        else:
            probas = self.clf.predict_proba(X_arr)
            res = np.asarray(probas, dtype=np.float64)

        assoc = association_map or getattr(self, "association_map", None)
        if assoc is not None:
            classes = self.classes_ if self.classes_ is not None else list(range(res.shape[1]))
            res = np.asarray(
                assoc.blend(res, X_arr, key=key, classes=classes),
                dtype=np.float64,
            )
        return res

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, p)

    def export_for_edge(self, output_dir: str | Path) -> dict[str, Any]:
        if not self.is_fitted:
            raise ClassifierNotTrainedError("Classifier must be fitted before export_for_edge")
        from geolearn.edge import export_edge_model

        return export_edge_model(self, output_dir)

    @classmethod
    def load(cls, path: str | Path) -> OnlineClassifier:
        obj = joblib.load(path)
        if not isinstance(obj, OnlineClassifier):
            raise TypeError(f"Loaded object is not OnlineClassifier: {type(obj)}")
        if not hasattr(obj, "choice"):
            obj.choice = ClassifierChoice.SGD
        if not hasattr(obj, "n_samples_"):
            obj.n_samples_ = 0
        return obj

