# GeoLearn — Core Framework

A new independent library `libs/geolearn/` that sits between GeoMemory and
GeoAgent. It consumes OLMoEarth embeddings (frozen) and produces per-class
predictions via an online classifier with `partial_fit()`. No PyTorch training
loop; no LoRA; no heavy ML framework in v1.

Core identity: **"River for remote sensing foundation model adapters"** — but
built on sklearn + numpy only for v1, with River as an optional `[river]` extra
for v2.

## Architecture

```
GeoMemory (OLMoEarth frozen embeddings)
        ↓
   GeoLearn
   ├── EmbeddingCache      — persistent cache of frozen embeddings by asset_id
   ├── OnlineClassifier    — SGDClassifier per (crop_type, region) key
   └── ConfidenceModel     — calibration curve for prediction confidence
        ↓
   GeoAgent (consumes predictions via tool results)
        ↓
   Feedback (via GeoMemory candidate memory) → trains next partial_fit cycle
```

## Requirements

### Requirement: Embedding cache
`EmbeddingCache(workspace_dir)` SHALL store `(asset_id → embedding_vector)` pairs
in a SQLite table (`geolearn.db`, separate from geomemory.db and agent.db).
Vectors are float32, read-only after write. Supports bulk insert and lookup by
asset_id or by nearest-neighbor within an epsilon radius.

#### Scenario: Cache lookup
- **WHEN** `cache.lookup(asset_id)` is called
- **THEN** the embedding vector (or None if absent) is returned

#### Scenario: Nearest-neighbor fallback
- **WHEN** a label is requested for an unseen asset_id and `k_nn=5`
- **THEN** the 5 nearest cached embeddings are returned with their labels

### Requirement: Online classifier interface
`OnlineClassifier` SHALL wrap `sklearn.linear_model.SGDClassifier` with
`partial_fit(classes=[0,1,2,...])`. It SHALL support:
- `fit(embeddings, labels)`: initial batch fit
- `partial_fit(embeddings, labels)`: incremental update
- `predict(embeddings) -> labels`
- `predict_proba(embeddings) -> probabilities`
- Persistence: `save(path)` / `load(path)` via joblib

#### Scenario: Incremental update
- **WHEN** `partial_fit(new_embeddings, new_labels)` is called after initial fit
- **THEN** the classifier weights are updated without retraining from scratch

### Requirement: Per-key classifiers
Classifiers are keyed by `(crop_type, region)`. Each key has its own classifier
instance. The default key is `("unknown", "global")`.

#### Scenario: Region-specific prediction
- **WHEN** `classifier.predict_for_key(["ndvi_array"], key=("wheat", "khuzestan"))`
- **THEN** the wheat/khuzestan-specific classifier is used; if none exists, a
  global fallback is used

### Requirement: Confidence modeling
Every prediction SHALL carry a confidence score:
- For SGDClassifier: use `predict_proba` max probability as confidence
- When confidence < threshold (default 0.6): signal abstention to the agent

#### Scenario: Low-confidence prediction
- **WHEN** max proba < 0.6
- **THEN** the result includes `confidence: 0.45, abstain: true`

### Requirement: No PyTorch in v1
GeoLearn v1 SHALL have zero PyTorch dependencies. Only numpy, scikit-learn,
sqlite3, joblib. This keeps it deployable on CPUs and edge devices.

### Requirement: Output contract
Every prediction call returns a `PredictionResult`:
```python
@dataclass
class PredictionResult:
    labels: list[int]
    confidence: list[float]       # parallel to labels
    abstain: bool                 # True if any confidence < threshold
    key: tuple[str, str]          # (crop_type, region)
    n_samples: int
    model_version: str            # sha256 of classifier state file
```

## Non-goals (v1)

- Concept drift detection (River feature — deferred to v2)
- Replay buffers
- Model ensembling
- Neural network adapters / LoRA

## Phase 3 note (documented separately)

Phase 3 changes (online-learning-engine, edge-deployment-runtime,
model-versioning-and-rollbacks, frozen-foundation-model-adapters) are recorded
in `docs/phase3-roadmap.md` inside `libs/geolearn/`. They are NOT part of this
change's scope.
