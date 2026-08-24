## Context

PDF ingestion today routes through `PdfLoader` (PyMuPDF) producing `text` + `{page:i}` locators. We add `OpenDataLoaderPdf` (ODL) as a higher-quality optional backend. ODL is a Python wrapper around a bundled 23 MB JAR executed via `subprocess` → `java -jar`; it requires Java 11+ on PATH (present on the dev box: OpenJDK 25) and emits reading-ordered Markdown + per-element JSON (type, page, bbox, id). Selection and fallback must preserve zero-dependency behavior for environments without the extra/Java.

## Goals / Non-Goals

**Goals:**
- Prefer ODL when available; transparently fall back to PyMuPDF otherwise.
- Carry page + bounding-box coordinates into `segment.locator` for precise citations.
- Keep the facade, schema, and public API unchanged.

**Non-Goals:**
- Not replacing `PdfLoader` (kept as fallback).
- Not persisting full ODL JSON in every `segment.metadata` (avoid row bloat).
- Not building the `odl_structure` element-typed chunker (deferred to phase 2).
- No change to offline/local-first posture (ODL is local; no network).

## Decisions

**D1 — Augment, not replace (Fork 1 = B).** Add `OpenDataLoaderPdf` and a selection rule; `PdfLoader` remains. Rationale: matches GeoMemory's lazy-optional-dep + graceful-degradation house style (cf. hashing embedder vs llama-cpp). Alternatives rejected: replacing `PdfLoader` would break zero-dep installs.

**D2 — Minimal locator persistence (Fork 3 = recommend).** `segment.locator = {page, bbox:[x1,y1,x2,y2], element_id, element_type}`. Full per-element JSON stays in `ParsedObject.metadata` (available for future dashboard highlighting) but is not written per segment. Rationale: keeps `segment`/`segments_fts` rows small; no schema migration needed.

**D3 — Phase-1 chunker = existing `header_then_token` (Fork 4 = recommend).** ODL Markdown feeds the current chunker. The element-typed `odl_structure` chunker is phase 2. Rationale: low risk, immediate quality win from reading order + tables; typed chunker is a separate, additive change.

**D4 — Loader selection rule.** `get_loader` prefers ODL when `import opendataloader_pdf` succeeds AND `shutil.which("java")` is truthy; else PyMuPDF. A small `java_available()` helper centralizes detection. A settings flag (`pdf_parser: "auto" | "opendataloader" | "pymupdf"`) allows forced selection.

**D5 — JVM batching.** Because `convert()` spawns a JVM per call, multi-file ingests collect paths and invoke `convert` once, then map outputs back by filename. Single-file ingest pays one cold-start (acceptable; matches ODL guidance).

## Risks / Trade-offs

- [Risk] Java absent on some target machines → ODL path raises at runtime. → Mitigation: selection only enables ODL when `java` detected; fallback always available. `doctor` can report Java status.
- [Risk] JVM cold-start latency on large batch ingests. → Mitigation: batch folder ingests into one `convert()` call (D5).
- [Risk] ODL output format drift across versions. → Mitigation: pin `opendataloader-pdf>=2.5,<3`; parse defensively (bbox optional).
- [Trade-off] Minimal locators mean dashboard bbox highlight needs the JSON re-derived or stored separately in phase 2.

## Migration Plan

1. Add extra; implement loader + selection; unit tests for selection/fallback.
2. Golden test: ingest a sample multi-column PDF, assert `segment.locator` contains `bbox` + `element_type`.
3. Rollback: the extra is optional; removing it reverts to PyMuPDF with no code change.

## Open Questions

- Should `pdf_parser` default to `"auto"` or expose a workspace setting? (Proposed: `auto`, overridable via `WorkspaceSettings`.)
- Phase-2 `odl_structure` chunker: track as a follow-up change, not here.
