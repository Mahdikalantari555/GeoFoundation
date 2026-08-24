# Design: fix-txtai-backend-and-e2e-tests

## Context

Two categories of pre-existing test failures were found during testing:

1. **TxtaiBackend bug** — `TxtaiBackend.db` passed `path=self.index_dir` to txtai's `Embeddings()` constructor, which treats it as a model identifier and tries to download from HuggingFace Hub. Additionally, `count()` used `len(self.db)` which txtai doesn't support.

2. **E2E test skip logic** — The playwright test didn't skip when no browser was found or server wasn't running. The txtai tests didn't skip when HuggingFace Hub was unreachable.

## Goals

- Fix `TxtaiBackend` to not pass a local path as a model identifier.
- Make integration/e2e tests skip gracefully when their runtime dependencies (network, browser, server) are unavailable.

## Decisions

### D1: Don't pass `path=` to txtai Embeddings
We use precomputed embeddings via `upsert()`. The `path=` argument is only for model identifiers. Remove it.

### D2: Use `db.count()` instead of `len(db)`
txtai's `Embeddings.count()` returns the number of indexed documents. Use that.

### D3: Skip integration tests when dependencies unavailable
- txtai tests: check HuggingFace Hub reachability via socket connection.
- playwright tests: check browser executable exists + dashboard server reachable.

## Non-Goals

- Not changing any public API.
- Not adding new test coverage (just making existing tests skip gracefully).
- Not modifying the txtai backend behavior beyond the bug fix.
