# GeoLearn — Core Framework Design

## Repository structure

```
libs/geolearn/
  pyproject.toml
  README.md
  geolearn/
    __init__.py
    core.py              # OnlineClassifier, PredictionResult, EmbeddingCache
    cache.py             # EmbeddingCache implementation (SQLite)
    classifier.py        # SGDClassifier wrapper + per-key management
    confidence.py        # ConfidenceModel — calibration & threshold logic
    persistence.py       # save/load via joblib + model version tracking
    exceptions.py        # GeoLearnError, ClassifierNotTrainedError
    cli/                 # (future) CLI for standalone training
    tests/
      test_classifier.py
      test_cache.py
      test_confidence.py
      test_persistence.py
  docs/
    phase3-roadmap.md    # Phase 3 changes documented here, not implemented
  openspec/
    project.md
    specs/
      core-framework/
        spec.md
```

## Database schema (geolearn.db)

```sql
CREATE TABLE embedding_cache (
  asset_id    TEXT PRIMARY KEY,
  embedding   BLOB NOT NULL,    -- numpy float32 serialized bytes
  created_at  TEXT NOT NULL     -- ISO timestamp
);

CREATE TABLE classifier_state (
  key_crop    TEXT NOT NULL,
  key_region  TEXT NOT NULL,
  version     TEXT NOT NULL,    -- sha256 of serialized classifier bytes
  fitted_at   TEXT NOT NULL,
  n_samples   INTEGER NOT NULL,
  PRIMARY KEY (key_crop, key_region)
);
-- Actual classifier bytes stored in <workspace>/geolearn/models/<key>/classifier.pkl
```

## Classification flow

```
1. Agent calls geo_predict(asset_id, crop_type?, region?)
2. GeoLearn looks up embedding for asset_id in EmbeddingCache
   - miss → returns abstention signal + request to enrich cache
   - hit  → proceeds
3. Selects classifier by (crop_type or "unknown", region or "global")
   - miss → falls back to default global classifier
4. predict_proba → labels + confidence
5. If confidence < threshold → abstain flag set
6. Returns PredictionResult
```

## Integration points

- **GeoMemory**: reads frozen embeddings from `geomemory.embeddings.OlmoEarthVisionEmbedder`;
  writes feedback events into `geomemory.feedback`. GeoLearn does NOT call GeoMemory
  directly — it receives embeddings as inputs from the caller.
- **GeoAgent**: exposes `geo_predict` and `geo_train_on_feedback` as tools.
- **Feedback loop**: `geo_train_on_feedback(feedback_events)` reads accepted
  corrections from GeoMemory's candidate memory and calls `partial_fit()` on
  the relevant classifier key.

## Dependencies

- Runtime: `numpy>=1.24`, `scikit-learn>=1.3`, `joblib>=1.3`
- Optional `[river]`: `river>=0.20` (Phase 2/3 only, NOT v1)
- No torch, no pytorch-lightning, no huggingface-transformers
