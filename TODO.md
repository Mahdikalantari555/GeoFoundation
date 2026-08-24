# TODO — deferred work

Things to do later, outside the agent session. Last updated: 2026-08-24.

## 1. Verify Docker build (`add-st-qdrant-docker` task 5.1 remainder)

Files `Dockerfile` and `docker-compose.yml` are written but **never built** —
the in-session build was stopped because pip downloads torch (~2 GB, slow).

```bash
cd /mnt/data/Projects/RSGIS/Thesis_Project/GeoMemory

# CLI image (expect several minutes on first run; torch is the bottleneck)
docker build --target cli -t geomemory:cli .
docker run --rm geomemory:cli --help          # must print usage, not traceback

# UI image (optional)
docker build --target ui -t geomemory:ui .
```

If the base→cli layer ordering makes torch re-download for `ui`, consider a
shared builder stage or `--mount=type=cache,target=/root/.cache/pip`.

## 2. Compose smoke test (task 5.3)

```bash
docker compose up --build -d
docker compose ps                              # qdrant + geomemory-ui both healthy
docker compose exec geomemory-ui geomemory \
  ingest tests/fixtures/sample.md --collection smoke   # or any fixture doc
# search via dashboard or:
docker compose exec geomemory-ui geomemory search "your query"
docker compose restart && docker compose ps    # data survives (named volumes)
docker compose down -v                         # cleanup when done
```

Success criteria: both services healthy, index+search round-trip works,
data persists across restart.

## 3. After Docker verification passes

1. Tick tasks 5.1 and 5.3 in
   `openspec/changes/add-st-qdrant-docker/tasks.md`.
2. Run final gates once more:
   ```bash
   conda run -n ai python -m pytest tests/ -q
   conda run -n ai ruff check src tests
   conda run -n ai python -m mypy --strict src/geomemory
   openspec validate add-st-qdrant-docker --strict
   ```
3. Sync delta specs → main specs and archive:
   `/opsx:archive add-st-qdrant-docker`
   (spec dirs: docker-deployment, qdrant-vector-backend,
   sentence-transformer-embeddings + touched workspace-management specs).

## Known unrelated issues (not blocking, fix whenever)

- `tests/integration/test_txtai_backend.py`: 3 failures
  (`test_upsert_and_count`, `test_hybrid_search_roundtrip`, `test_delete`).
  Verified they fail identically on clean HEAD — environmental: txtai/transformers
  tries to reach the Hugging Face hub and treats the local index dir as a repo id.
  Likely needs network or an offline-mode env var (`HF_HUB_OFFLINE=1`) /
  txtai config fix; investigate separately.
- Pre-existing ruff E501s in `core/models.py` (2) and `core/workspace.py` (8)
  untouched by this change — clean up in a dedicated lint pass if desired.
