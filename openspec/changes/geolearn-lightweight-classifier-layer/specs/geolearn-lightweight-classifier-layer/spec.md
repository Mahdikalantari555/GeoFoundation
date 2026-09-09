# geolearn-lightweight-classifier-layer — Specification (v0.2)

Adds alternative online classifiers alongside SGDClassifier under a unified interface.

## Requirements

### Requirement: ClassifierChoice enum
```python
class ClassifierChoice(str, Enum):
    SGD = "sgd"
    PASSIVE_AGGRESSIVE = "passive_aggressive"
    INCREMENTAL_KMEANS = "incremental_kmeans"
```

### Requirement: Unified partial_fit interface
All choices SHALL implement the same method signatures:
- `fit(X, y, classes=None)` → self
- `partial_fit(X, y)` → self
- `predict(X) -> ndarray[int]`
- `predict_proba(X) -> ndarray[float]` (PA returns probabilities via decision_function)
- `n_samples_ -> int`

#### Scenario: PassiveAggressiveClassifier
- **WHEN** constructed with `C=1.0, max_iter=1000, tol=1e-3`
- **THEN** it accepts the same `partial_fit(X, y)` calls as SGDClassifier
- **THEN** it is more robust to noisy labels (tolerates mislabeled samples better)

#### Scenario: IncrementalKMeans
- **WHEN** called with unlabeled data (`y=None`)
- **THEN** it forms clusters without requiring labels (semi-supervised mode)
- **THEN** `predict()` returns cluster assignments

### Requirement: Default remains SGD
`ClassifierChoice.SGD` is the default. Switching requires explicit configuration.

### Requirement: Persistence compatibility
All three classifiers serialize/deserialize via joblib; saved models from v1
(SGD only) continue to load in v2.

## Non-goals

- Ensemble methods combining multiple classifiers
- Neural network adapters (reserved for future)
- Auto-tuning hyperparameters
