# Tasks

## 1. Dependency & packaging
- [x] Add optional extra `opendataloader` (`opendataloader-pdf>=2.5,<3`) to `pyproject.toml`.
- [x] Document the extra in README install instructions (optional step).

## 2. Java detection helper
- [x] Add `java_available() -> bool` helper (e.g. in `ingest/loaders/base.py` or `core/`), using `shutil.which("java")`.
- [x] Surface Java status in `services/doctor.py` diagnostics.

## 3. OpenDataLoader PDF loader
- [x] Create `ingest/loaders/opendataloader_pdf.py` with `OpenDataLoaderPdf` (implements `Loader`).
  - `supports()`: `.pdf` extension.
  - `load()`: invoke `opendataloader_pdf.convert(...)` (batch input paths when possible), parse output; produce `ParsedObject(text=reading-ordered markdown, metadata={locators:[{page,bbox,element_id,element_type}], odl: <full json>})`.
  - Lazy-import `opendataloader_pdf`; raise a clear error if missing.
- [x] Keep `text` reading-ordered and tables intact for the existing chunkers.

## 4. Loader selection & fallback
- [x] Wire `OpenDataLoaderPdf` into `default_registry()` so it is preferred for `application/pdf` when `java_available()` and importable.
- [x] Ensure `PdfLoader` remains the fallback path; no behavior change when ODL/Java absent.
- [x] Add optional `pdf_parser` setting (`auto|opendataloader|pymupdf`) honored by selection.

## 5. Locator contract
- [x] Persist minimal ODL locator `{page, bbox, element_id, element_type}` on segments (no full JSON per segment).
- [ ] Confirm dashboard/review can consume bbox locators (read-only; rendering is phase 2).

## 6. Tests
- [x] Unit: `OpenDataLoaderPdf.supports` / fallback selection logic (mock import + java check).
- [x] Unit: locator shape assertion from a parsed fixture.
- [x] Integration/golden: ingest a sample multi-column PDF; assert `segment.locator` includes `bbox` + `element_type`.
- [x] Integration: ingestion still works with ODL/Java absent (PyMuPDF path).

## 7. Docs
- [x] Update `AGENTS.md` / `docs/current-state/` loader list to mention `OpenDataLoaderPdf`.
- [ ] Note phase-2 `odl_structure` chunker as future work.

## Out of scope (phase 2)
- [ ] `odl_structure` chunker mapping ODL elements → `SegmentDraft.segment_type`.
- [ ] Dashboard bbox highlight rendering from locators.
