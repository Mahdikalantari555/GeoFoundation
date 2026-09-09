# Tasks: geospatial-knowledge-layer

- [ ] Task 1: Entity model + schema
  - Acceptance: `Entity` Pydantic model added to `core/models.py`; `entity` table added to `schema.sql` with columns `{id, name, kind, workspace_id, spatial_bbox, created_at}`; migration v2 registered in `migrations.py`.
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests/unit/test_database.py -v` (migration runs cleanly on fresh DB).
  - Files: `src/geomemory/core/models.py`, `src/geomemory/storage/schema.sql`, `src/geomemory/storage/migrations.py`

- [ ] Task 2: Entity repository
  - Acceptance: `EntityRepository` in `storage/repositories/entity_repo.py` with `create`, `get`, `list_by_kind`, `list_by_workspace`, `upsert_name_match(name, kind)` (returns existing if name+kind match, else creates).
  - Verify: unit tests for create, get, upsert_name_match dedup behavior.
  - Files: `src/geomemory/storage/repositories/entity_repo.py`, `tests/unit/test_entity_repo.py`

- [ ] Task 3: EntityExtractor protocol + RuleBasedExtractor
  - Acceptance: `EntityExtractor` protocol defined in `knowledge/extractors.py`; `RuleBasedExtractor` implements it using regex patterns for common RS terms (NDVI, EVI, EC, salinity, drought, etc.); returns list of `(name, kind, bbox|None)` tuples.
  - Verify: unit tests — known patterns extracted, unknown text returns empty list.
  - Files: `src/geomemory/knowledge/extractors.py`, `tests/unit/test_extractors.py`

- [ ] Task 4: LLM-driven extractor (optional, gated on LLM availability)
  - Acceptance: `LLMEntityExtractor` implements `EntityExtractor`; prompts the configured LLM backend with structured output format; parses JSON response into entity list. Falls back to `RuleBasedExtractor` when LLM is unavailable.
  - Verify: integration test with fake LLM backend returning structured JSON; graceful fallback test.
  - Files: `src/geomemory/knowledge/extractors.py` (extends), `tests/integration/test_llm_extractor.py`

- [ ] Task 5: Ingest pipeline integration
  - Acceptance: `IngestionPipeline.ingest_source()` calls the configured extractor after segment persistence; errors are caught and logged without aborting ingest; extracted entities are persisted via `EntityRepository`.
  - Verify: integration test — ingest a document mentioning "NDVI"; assert entity row exists post-ingest.
  - Files: `src/geomemory/ingest/pipeline.py`

- [ ] Task 6: Proposal approval extended to populate entities
  - Acceptance: `ProposalEngine.review(approve=True)` atomically creates/links entity rows and inserts relation rows when `proposal_type="graph_relation"`; diff format `{"source": str, "predicate": str, "target": str}` is parsed.
  - Verify: unit test — approve a graph_relation proposal; assert entity and relation rows exist.
  - Files: `src/geomemory/feedback/proposals.py`

- [ ] Task 7: Traverse API
  - Acceptance: `Workspace.traverse(entity_id, depth=1)` returns entity dict plus relations (capped at depth 3, max 50 total hits). Exposed via server router `GET /api/v1/entities/{id}/traverse`.
  - Verify: server test — traverse a known entity returns relations; traverse nonexistent entity returns 404.
  - Files: `src/geomemory/core/workspace.py`, `server/src/geofront_api/routers/entities.py` (new), `server/tests/test_entities.py`

- [ ] Task 8: Expand-relations search mode
  - Acceptance: `SearchRequest` gains optional `expand_relations: bool`; `Workspace.search()` when true looks up entities linked to top hits and appends their related segments (capped at 50) after primary results.
  - Verify: integration test — search with expand_relations=True on workspace with entities returns primary + supplementary hits.
  - Files: `src/geomemory/core/models.py`, `src/geomemory/core/workspace.py`, `tests/integration/test_search_expand.py`

- [ ] Task 9: Web entity page
  - Acceptance: New `apps/web/src/features/knowledge/EntitiesPage.tsx` listing entities filtered by kind; clicking an entity shows its relations in a simple list. Wired into router under `/knowledge/entities`.
  - Verify: `pnpm test` passes; manual browser smoke test.
  - Files: `apps/web/src/features/knowledge/EntitiesPage.tsx`, `apps/web/src/features/knowledge/hooks.ts`, `apps/web/src/app/router.tsx`

- [ ] Task 10: Gates
  - Acceptance: full geomemory + server test suites green; ruff/mypy clean; web build succeeds.
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests server/tests -q && conda run -n geospatial ruff check libs/geomemory/src server/src && conda run -n geospatial mypy --strict libs/geomemory/src/geomemory && cd apps/web && pnpm build`
  - Files: all above

Dependencies: 1→2, 2+3→4 (LLM extractor uses repo), 3→5 (pipeline uses extractor), 6 independent (uses repo from 2), 7 depends on 2, 8 depends on 2+5, 9 depends on 7 (API), all→10.
