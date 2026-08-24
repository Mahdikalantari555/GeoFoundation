# Proposal: fix-txtai-backend-and-e2e-tests

## Why

Two categories of test failures existed that were unrelated to the changes being made:

1. **TxtaiBackend bug**: `TxtaiBackend.__init__` passed `path=self.index_dir` to txtai's `Embeddings()`, which interprets `path=` as a model identifier and attempts to download it from HuggingFace Hub. This caused 3 integration tests to fail with `OSError: Repo id must be in the form 'repo_name' or 'namespace/repo_name'`. Additionally, `count()` used `len(self.db)` but txtai's `Embeddings` class doesn't implement `__len__`.

2. **E2E test skip logic**: The playwright dashboard test didn't skip when no browser executable was found or when the dashboard server wasn't running, causing hard failures instead of graceful skips. The txtai integration tests didn't skip when HuggingFace Hub was unreachable.

## What Changes

- Remove `path=self.index_dir` from txtai `Embeddings()` constructor in `TxtaiBackend.db` property — we use precomputed embeddings supplied via `upsert()`, not model inference.
- Fix `TxtaiBackend.count()` to use `self.db.count()` instead of `len(self.db)`.
- Simplify `TxtaiBackend.search()` by removing redundant mode branches (all modes use the same `db.search()` call).
- Add proper skip conditions to playwright e2e test: skip if no browser executable found, skip if dashboard server not reachable on localhost:8501.
- Add network availability check to txtai integration tests: skip if HuggingFace Hub is unreachable.

## Capabilities

### Modified Capabilities
- `txtai-backend`: fixed model-path misinterpretation and count() contract; tests now skip gracefully when network unavailable.
- `e2e-dashboard-test`: skips gracefully when browser or server unavailable instead of failing hard.

## Impact

- **Code**: `src/geomemory/index/txtai_backend.py` (bug fix), `tests/e2e/test_dashboard_playwright.py` (skip logic), `tests/integration/test_txtai_backend.py` (skip logic).
- **APIs**: none broken.
- **Dependencies**: none changed.
- **Tests**: all 362 tests pass; 1 e2e test skips gracefully when server not running.
