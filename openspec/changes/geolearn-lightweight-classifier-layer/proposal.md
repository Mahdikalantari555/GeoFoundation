## Why

SGDClassifier is sufficient for v1 but too rigid for real agricultural data:
concepts drift seasonally, some crops need different decision boundaries, and
pure linear models plateau. This change expands the classifier layer with
additional sklearn online learners, keeping the same `partial_fit()` interface
so switching models is a configuration choice, not a refactor.

## What Changes

1. Add `PassiveAggressiveClassifier` and `IncrementalKMeans` as alternative
   classifiers under the same `OnlineClassifier` interface.
2. Add a `ClassifierChoice` enum (`sgd, passive_aggressive, incremental_kmeans`).
3. Each choice gets its own `partial_fit` semantics documented in the spec.
4. Default remains `sgd`; `passive_aggressive` is recommended for noisy
   agricultural labeling; `incremental_kmeans` enables clustering-based
   adaptation when no labeled data exists yet.

## Capabilities

### New Capabilities
- `geolearn-classifier-layer`: multi-alternative online classifier implementations.

## Impact

- Adds ~150 lines to `geolearn/classifier.py`.
- No new dependencies (all classifiers are in scikit-learn).
- Backward-compatible: existing `sgd` path unchanged.
