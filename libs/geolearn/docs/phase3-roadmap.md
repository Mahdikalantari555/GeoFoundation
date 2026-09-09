# GeoLearn Phase 3 Roadmap (Future Changes)

These changes are documented here for future implementation. They are NOT part
of the current rollout — see the corresponding openspec change proposals for
full specs.

## Phase 3 Changes

| # | Change | Description | Dependency |
|---|---|---|---|
| 12 | `geolearn-online-learning-engine` | River-style streaming windows, drift detection (PageHinkley), scheduled training cycles. Optional `[river]` extra. | Core framework complete |
| 13 | `geolearn-personalization-profiles` | Persistent user+region profiles with preferred classifier selection. | Core framework complete |
| 14 | `geolearn-frozen-foundation-model-adapters` | NN fallback over frozen OLMoEarth embeddings when classifier has <30 samples. | Core framework + EmbeddingCache |
| 15 | `geolearn-feedback-to-training-pipeline` | Wire candidate memory accepted corrections → partial_fit() batch updates. | Core framework + Change 1 (candidate memory) |
| 16 | `geolearn-lightweight-classifier-layer` | Add PassiveAggressiveClassifier and IncrementalKMeans as alternatives to SGDClassifier. | Core framework complete |
| 17 | `geolearn-incremental-embedding-learning` | Association map with exponential decay overlay on top of classifier predictions. | Core framework complete |
| 18 | `geolearn-region-specific-adaptation` | Hierarchical per-region classifier keys (crop.region.subregion) with weight transfer from parent. | Core framework complete |
| 19 | `geolearn-user-specific-adaptation` | Per-user confidence threshold and behavior preferences stored in geolearn.db. | Personalization profiles |
| 20 | `geolearn-edge-deployment-runtime` | JSON+numpy export format + EdgeLoader (no sklearn needed at runtime). | Core framework complete |
| 21 | `geolearn-confidence-and-uncertainty-modeling` | Isotonic calibration curve + entropy-based uncertainty for reliable abstention. | Core framework complete |
| 22 | `geolearn-model-versioning-and-rollbacks` | Versioned classifier saves (last 10) with rollback-to-prior-state support. | Core framework complete |

## Recommended Execution Order

1. Core framework (Change 6) — foundation for everything
2. Feedback-to-training (Change 10) — gives the system its learning signal
3. Confidence modeling (Change 21) — makes predictions trustworthy
4. Region-specific adaptation (Change 18) — enables multi-region deployment
5. User-specific adaptation (Change 19) — personalization layer
6. Lightweight classifier layer (Change 16) — more model options
7. Online learning engine (Change 12) — streaming + drift detection
8. Frozen adapter (Change 14) — cold-start bridge
9. Incremental embedding learning (Change 17) — association map refinement
10. Edge deployment (Change 20) — portable export
11. Model versioning (Change 22) — safety net for production

## Key Design Decisions

- **No PyTorch in v1**: All classifiers are sklearn-compatible; River is optional.
- **Separate db**: `geolearn.db` lives alongside `geomemory.db` and `agent.db`.
- **Feedback-driven**: Training signals come from GeoMemory candidate memory (Change 1).
- **Edge-first**: Every component must run on CPU without CUDA.
