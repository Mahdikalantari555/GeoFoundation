# pdf-ingestion Specification

## Purpose
PDF ingestion for GeoMemory: parse PDF assets into searchable, citable segments, preferring the highest-quality available parser while always preserving a zero-dependency fallback.
## Requirements
### Requirement: PDF parser selection
The system SHALL select a PDF parser at ingestion time, preferring `opendataloader-pdf` when the optional extra is installed and a Java runtime is available, and otherwise falling back to the PyMuPDF-based loader.

#### Scenario: High-quality parser available
- **WHEN** a PDF is ingested and `opendataloader-pdf` is importable and `java` is on PATH
- **THEN** the system uses `opendataloader-pdf` to extract reading-ordered content

#### Scenario: Fallback when unavailable
- **WHEN** a PDF is ingested and either the extra is missing or no Java runtime exists
- **THEN** the system uses the PyMuPDF loader and ingestion still succeeds

#### Scenario: Forced selection
- **WHEN** a workspace setting forces `pdf_parser` to a specific backend
- **THEN** the system uses only that backend (subject to availability)

### Requirement: Bounding-box locators
PDF segments produced by `opendataloader-pdf` SHALL carry source coordinates in their locator: `page`, `bbox` ([x1, y1, x2, y2]), `element_id`, and `element_type`.

#### Scenario: Precise citation coordinates
- **WHEN** a PDF chunk is ingested via `opendataloader-pdf`
- **THEN** its locator includes page and bounding-box so a citation can highlight the exact region

