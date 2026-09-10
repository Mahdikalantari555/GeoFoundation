# Design: geolearn-lightweight-classifier-layer

Extends geolearn-core-framework with alternative online classifiers under a unified interface.

## Module layout

```
geolearn/classifier.py   # OnlineClassifier (existing) + ClassifierChoice enum
```

## ClassifierChoice enum

```python
from enum import Enum

class ClassifierChoice(str, Enum):
    SGD = "sgd"
    PASSIVE_AGGRESSIVE = "passive_aggressive"
    INCREMENTAL_KMEANS = "incremental_kmeans"
```

## Implementation strategy

`OnlineClassifier` gains a `choice` parameter at construction. The internal
wrapped model is selected based on `choice`:

| Choice | sklearn class | Key params | Notes |
|---|---|---|---|
| `sgd` | `SGDClassifier(loss="modified_huber")` | random_state=42 | Default; supports partial_fit out of box |
| `passive_aggressive` | `PassiveAggressiveClassifier` | C=1.0, max_iter=1000, tol=1e-3 | More robust to noisy labels |
| `incremental_kmeans` | `MiniBatchKMeans` | n_clusters=None (inferred), batch_size=256 | Semi-supervised: accepts y=None |

## Interface compatibility

All three classes implement the same public methods:
- `fit(X, y, classes=None)` — initial fit
- `partial_fit(X, y)` — incremental update
- `predict(X) -> ndarray[int]`
- `predict_proba(X) -> ndarray[float]` (PA uses calibrated decision_function; KMeans returns cluster proximity)

## Persistence

All three serialize via `joblib.dump`/`joblib.load`. Saved SGD models remain
loadable when choice is changed (backward-compatible).
