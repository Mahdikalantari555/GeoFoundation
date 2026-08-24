## Why

GeoMemory's PDF ingestion uses PyMuPDF (`PdfLoader`), which extracts text per page but loses reading order, table structure, and source coordinates — exactly the quality ceiling that hurts RAG retrieval and citation precision. `opendataloader-pdf` (Apache-2.0, local-first, benchmark #1 for RAG PDF parsing) produces reading-ordered Markdown plus per-element bounding boxes, page numbers, and semantic types. Adding it as an optional high-quality PDF backend strengthens the provenance/citation story (ADR-0007) without breaking the zero-dependency fallback path.

## What Changes

- Add a new optional dependency extra `opendataloader` (`opendataloader-pdf`, v2.5.x) to `pyproject.toml`.
- Add `OpenDataLoaderPdf` loader (`ingest/loaders/opendataloader_pdf.py`): wraps `opendataloader_pdf.convert(...)`; emits reading-ordered Markdown as `text` and per-element `{page, bbox, element_id, element_type}` as locators.
- Keep `PdfLoader` (PyMuPDF) as the **zero-dependency fallback**. PDF loader selection prefers `OpenDataLoaderPdf` when (a) the `opendataloader` extra is importable and (b) a `java` executable is on PATH; otherwise falls back to `PdfLoader`. No behavior change for environments without Java/extra.
- Loader selection integrated into `default_registry()` / `get_loader()` so existing ingestion flow is unchanged.
- Locator schema: ODL-parsed PDFs carry `{page, bbox:[x1,y1,x2,y2], element_id, element_type}` instead of the current `{page:i}`. Dashboard citation rendering can later highlight the exact region (phase 2).
- Persist **minimal** ODL metadata only (locators); the full per-element JSON stays in `ParsedObject.metadata`, not forced into every `segment.metadata` (avoids row bloat).
- **Phase 2 (out of scope here):** add an `odl_structure` chunker that maps ODL elements directly to `SegmentDraft.segment_type` (paragraph/table/heading/cell) — reuses the existing enum, no schema change. Deferred to keep this change small.

## Capabilities

### New Capabilities
- `pdf-ingestion`: describes PDF ingestion behavior — parser selection (ODL preferred, PyMuPDF fallback), output contract (reading-ordered text + bbox/page locators), and the Java/extra graceful-degradation rule.

### Modified Capabilities
- `ingestion`: add a requirement that ingestion SHALL select the best available PDF parser and SHALL preserve source coordinates (page + bbox) in segment locators when the parser provides them.

## Impact

- **Code**: new `ingest/loaders/opendataloader_pdf.py`; edits to `ingest/loaders/__init__.py` (registry + fallback selection); possible small helper to detect Java availability (reuse pattern from `services/doctor.py`).
- **APIs**: none (facade `ingest` unchanged). Public surface unaffected.
- **Dependencies**: new optional extra `opendataloader` (parser bundles a 23 MB JAR; requires Java 11+ at runtime — already present on the dev machine, OpenJDK 25). Not a base dependency; lazy-imported.
- **Operational**: `convert()` spawns a JVM per call; multi-file ingests should batch paths into a single `convert()` invocation to amortize cold-start (design note, not a blocker).
- **Tests**: unit tests for loader selection + fallback; golden/integration test ingesting a sample PDF and asserting bbox locators present.
- **Specs/ADRs**: no ADR change (honors local-first/offline: ODL is a local dependency, no network).
