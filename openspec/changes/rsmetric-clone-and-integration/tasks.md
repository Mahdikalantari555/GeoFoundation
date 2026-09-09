# Tasks: rsmetric-clone-and-integration

- [ ] Task 1: Clone and strip git
  - Acceptance: `libs/rsmetric/.git` does not exist; `git status` from repo root lists `libs/rsmetric/` as new untracked content.
  - Verify: `rm -rf libs/rsmetric/.git && ls libs/rsmetric/` shows package structure.
  - Files: none (new directory created)
  - Note: This task MUST be executed manually; automation is not part of the change.

- [ ] Task 2: Rename package from metric_et to rsmetric
  - Acceptance: `import rsmetric` resolves; `from rsmetric import METRICPipeline` works; all internal imports updated (`metric_et.X` → `rsmetric.X`).
  - Verify: `conda run -n geospatial python -c "import rsmetric; print(rsmetric.__version__)"` prints `0.1.0`.
  - Files: all `*.py` under `libs/rsmetric/rsmetric/`; `pyproject.toml`; `README.md`

- [ ] Task 3: Remove research scaffolding files
  - Acceptance: `Fetch_Data.py`, `Calculate_et.py`, `calculate_et_planetary.py`, `interpolate_et.py`, `run_metric_workflow.py`, `WORKFLOW_USAGE.md`, `scripts/`, `examples/`, `uv.lock` are absent from `libs/rsmetric/`.
  - Verify: `ls libs/rsmetric/*.py libs/rsmetric/*.md` lists only `README.md`.
  - Files: deleted files

- [ ] Task 4: Rewrite pyproject.toml
  - Acceptance: `name = "rsmetric"`, `requires-python = ">=3.10"`, `[project.scripts] rsmetric`, `[optional-dependencies] rs` covers all RS deps.
  - Verify: `conda run -n geospatial pip install -e libs/rsmetric` succeeds; `rsmetric --help` shows click commands.
  - Files: `libs/rsmetric/pyproject.toml`

- [ ] Task 5: Fix ruff/mypy violations introduced by rename
  - Acceptance: `conda run -n geospatial ruff check libs/rsmetric/src` reports 0 errors; `mypy --strict libs/rsmetric/src` reports 0 errors (or pre-existing errors documented and accepted).
  - Verify: same commands above return exit code 0.
  - Files: all touched `*.py` under `libs/rsmetric/rsmetric/`

- [ ] Task 6: Add rs_compute_et tool to geoagent
  - Acceptance: `rs_compute_et` appears in `geoagent.registry.Registry.names()`. Calling it with a valid Landsat dir writes ET products and returns artifact refs + stats dict. `[rs]` extra missing yields structured error naming the extra.
  - Verify: `conda run -n geospatial python -c "from geoagent.registry import Registry; r=Registry(); print('rs_compute_et' in r.names())"` is True (after tool registration).
  - Files: `libs/geoagent/src/geoagent/tools/rs_tools.py` (new), `libs/geoagent/src/geoagent/__init__.py` (export), `libs/geoagent/pyproject.toml` (add `[rs]` extra with rsmetric dep)

- [ ] Task 7: Update geoagent pyproject.toml
  - Acceptance: `[project.optional-dependencies] rs = ["rsmetric"]` present; base deps unchanged.
  - Verify: `conda run -n geospatial pip install -e libs/geoagent[rs]` installs both geoagent and rsmetric.
  - Files: `libs/geoagent/pyproject.toml`

- [ ] Task 8: Gates
  - Acceptance: `libs/rsmetric` passes its own pytest suite; geoagent tests pass; ruff clean across both libs.
  - Verify: `conda run -n geospatial pytest libs/rsmetric/tests -q && conda run -n geospatial pytest libs/geoagent/tests -q && conda run -n geospatial ruff check libs/rsmetric/src libs/geoagent/src`
  - Files: all above

Dependencies: 1→2→3→4 (sequential clone-work), 5 depends on 4, 6 depends on 4+5, 7 independent, all→8.
