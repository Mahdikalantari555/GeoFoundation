# Tasks: fix-txtai-backend-and-e2e-tests

## 1. TxtaiBackend bug fix

- [x] 1.1 Remove `path=self.index_dir` from `TxtaiBackend.db` property in `src/geomemory/index/txtai_backend.py`
- [x] 1.2 Fix `count()` to use `self.db.count()` instead of `len(self.db)`
- [x] 1.3 Simplify `search()` by removing redundant mode branches

## 2. Test skip logic

- [x] 2.1 Add browser executable + dashboard server reachability checks to `tests/e2e/test_dashboard_playwright.py`; skip if unavailable
- [x] 2.2 Add HuggingFace Hub reachability check to `tests/integration/test_txtai_backend.py`; skip if unreachable

## 3. Quality gates

- [x] 3.1 `ruff check` clean on all touched files
- [x] 3.2 `mypy --strict` passes on `src/geomemory/index/txtai_backend.py`
- [x] 3.3 Full `pytest` suite green (362 passed, 1 skipped)
