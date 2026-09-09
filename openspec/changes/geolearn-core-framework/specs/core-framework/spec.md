# geolearn-core-framework — Specification (v0.1)

## Requirements

### Requirement: EmbeddingCache API
`EmbeddingCache(workspace_dir)` SHALL provide `insert(asset_id, vector)`,
`lookup(asset_id) -> vector|None`, `nn_lookup(vector, k) -> list[(asset_id, dist)]`.
Storage is SQLite (`geolearn.db`) with a `vector` column as BLOB (numpy-serialized float32).

#### Scenario: Insert and retrieve
- **WHEN** `cache.insert("asset_1", np.ones(128, dtype=np.float32))`
- **THEN** `cache.lookup("asset_1")` returns the identical array

#### Scenario: Nearest neighbor
- **WHEN** 5 embeddings are cached and `nn_lookup(query, k=3)` is called
- **THEN** 3 `(asset_id, euclidean_distance)` tuples are returned sorted by distance

### Requirement: OnlineClassifier API
`OnlineClassifier(default_classes)` SHALL wrap `SGDClassifier(random_state=42)`.
Methods: `fit(X, y)`, `partial_fit(X, y)`, `predict(X) -> ndarray`,
`predict_proba(X) -> ndarray`, `save(path)`, `load(path)`. `classes` must be
provided on first `partial_fit` call.

#### Scenario: First partial_fit requires classes
- **WHEN** `clf.partial_fit(X, y)` is called without prior `fit`
- **THEN** classes inferred from `y` are stored and subsequent calls accept them

#### Scenario: Predict after fit
- **WHEN** `fit([[1,2],[3,4]], [0,1])` then `predict([[2,3]])`
- **THEN** label is returned (no abstention unless confidence < threshold)

### Requirement: ConfidenceModel
`ConfidenceModel(threshold=0.6)` SHALL evaluate max-proba from `predict_proba`
and return `abstain=True` when below threshold. Threshold is configurable per
instance.

#### Scenario: Abstention on low confidence
- **WHEN** predict_proba returns `[0.3, 0.7]` with threshold 0.6
- **THEN** abstain=True; predicted class is still 1 but flagged

### Requirement: Per-key classifier store
`ClassifierStore(workspace_dir)` SHALL manage one classifier per
`(crop_type, region)` key, defaulting to `("unknown", "global")`. Keys are
stored in `classifier_state` table; actual classifier bytes in
`<workspace>/geolearn/models/<crop>__<region>/classifier.pkl`.

### Requirement: PredictionResult dataclass
```python
@dataclass
class PredictionResult:
    labels: list[int]
    confidence: list[float]
    abstain: bool
    key: tuple[str, str]
    n_samples: int
    model_version: str
```

### Requirement: No torch dependency in v1
`import geolearn` SHALL succeed without PyTorch installed. If `river` is
requested via `[river]` extra, it is imported lazily inside functions only.

## Non-goals

- Concept drift detection
- Replay buffer
- Neural adapter layers
- Multi-model ensembling
