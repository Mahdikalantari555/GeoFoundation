# GeoFoundation — Structure & Conventions

## Artifact taxonomy

| Artifact | Examples | Travels as |
|---|---|---|
| Library | geomemory, geoagent, metric_et | pip package (git tag / path dep) |
| Gateway | server/ | container / uvicorn |
| App | apps/web, CLI, (future) MCP | static bundle / binary / protocol server |
| Workspace | SQLite + objects/ + runs/ | filesystem dir, zip archive — **never pip, never git** |
| Model weights | GGUF, .pth | model cache dir — **never git** |
| Case study | experiment code + configs + evals | own folder/repo with pinned deps + lockfile |

## Conda env

All Python work runs in the `ai` conda env (see geomemory CLAUDE.md):

```bash
conda run -n ai pip install -e libs/geomemory -e libs/geoagent
conda run -n ai python -m pytest libs/geomemory/tests -q
```

Known pre-existing failure (unrelated to monorepo):
`geomemorytest/test_workspace_lifecycle.py::TestAskAbstention::test_ask_no_model_abstains_when_context_exists`.

## Adding a library

1. Folder lands in `libs/<name>/` with src-layout + pyproject + tests.
2. `pip install -e libs/<name>` into `ai`.
3. Import name = folder name (naming symmetry, zero surprises).
4. Tag before anything pins it: `git tag libs/<name>/v0.1.0`.
5. Importing metric_et later: copy the package (setup.py → keep until a
   pyproject migration), `git add libs/metric_et`, editable install.

## Subtree note (history preservation)

`libs/geomemory` was imported with full history:

```bash
git subtree add --prefix=geomemory ../GeoMemory main
git mv geomemory libs/geomemory
```

If metric_et should keep ITS history when added, same pattern:
`git subtree add --prefix=libs/metric_et /media/E/RSGIS/SatAgrySys/METRICserver/metric_et main`
(requires metric_et to be a git repo first — it is not yet; plain copy is fine
too, history can start at v0.1.0 here).

Legacy siblings (`../GeoMemory`, `../GeoAgent`, `../geomemorytest`) are now
frozen copies — delete them only after confirming the monorepo works for a
few days. Do NOT edit them anymore.

## Case-study pattern (studies/, post-MSc or when first experiment starts)

```
studies/<name>/
├── pyproject.toml      # git-tag pinned deps + [tool.uv.sources] editable override
├── configs/            # yaml experiment configs
├── scripts/            # ingest.py · run.py · eval.py · report.py
├── evals/              # benchmark JSONLs (small, committed)
└── README.md           # workspace/model paths, how to reproduce
```

Dual-mode dependency trick (dev editable ↔ defense freeze):

```toml
[project]
dependencies = [
  "geomemory @ git+https://github.com/Mahdikalantari555/GeoFoundation.git@libs/geomemory/v0.1.0",
]

[tool.uv.sources]           # DEV ONLY — comment out + `uv lock` to freeze
geomemory = { path = "../../libs/geomemory", editable = true }
```

Rules:
- Studies touch only public facades (geomemory API, geoagent SDK). Needing
  an internal = feature request to the lib.
- Extract on second use: study-specific code graduates into `libs/` only
  when a second consumer appears (this is how GeoLearn will be born).
- Data/models/workspaces never committed; paths documented per-study.

## Versioning

- Monorepo trunk = `main`.
- Per-lib tags: `libs/<name>/vX.Y.Z` (subtree-friendly, unambiguous).
- Pre-1.0: exact pins everywhere (`==` / exact git tag).

## Git hygiene

- `workspace/`, `.env`, models, node_modules, venvs are gitignored globally.
- One concern per commit; `libs/` changes never mixed with app changes.
- Monorepo has no remote yet — add one before the next big milestone.
