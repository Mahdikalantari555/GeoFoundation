-- GeoMemory initial schema — version 1.
-- See .agent/spec/docs/Database Design.md for the authoritative design.

PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────────────────────────────────────
-- Workspace & collections
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS workspace (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    settings    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS collection (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    description  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    archived     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_collection_workspace ON collection(workspace_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- Assets & revisions
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS asset (
    id                  TEXT PRIMARY KEY,
    collection_id       TEXT NOT NULL REFERENCES collection(id) ON DELETE CASCADE,
    kind                TEXT NOT NULL,
    title               TEXT,
    current_revision_id TEXT,
    deleted_at          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    metadata            TEXT DEFAULT '{}',
    CHECK (kind IN ('document', 'code', 'raster', 'vector', 'table'))
);
CREATE INDEX IF NOT EXISTS idx_asset_collection ON asset(collection_id);
CREATE INDEX IF NOT EXISTS idx_asset_kind ON asset(kind);

CREATE TABLE IF NOT EXISTS asset_revision (
    id             TEXT PRIMARY KEY,
    asset_id       TEXT NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    hash           TEXT NOT NULL,
    mime_type      TEXT NOT NULL,
    size_bytes     INTEGER NOT NULL,
    parser_version TEXT NOT NULL,
    ingested_at    TEXT NOT NULL DEFAULT (datetime('now')),
    metadata       TEXT DEFAULT '{}',
    UNIQUE (asset_id, hash)
);
CREATE INDEX IF NOT EXISTS idx_revision_asset ON asset_revision(asset_id);
CREATE INDEX IF NOT EXISTS idx_revision_hash ON asset_revision(hash);

-- ─────────────────────────────────────────────────────────────────────────────
-- Segments + FTS5
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS segment (
    id                TEXT PRIMARY KEY,
    revision_id       TEXT NOT NULL REFERENCES asset_revision(id) ON DELETE CASCADE,
    segment_type      TEXT NOT NULL,
    text              TEXT NOT NULL,
    locator           TEXT NOT NULL DEFAULT '{}',
    parent_section_id TEXT,
    neighbor_ids      TEXT DEFAULT '[]',
    metadata          TEXT DEFAULT '{}',
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (segment_type IN ('paragraph', 'table', 'formula', 'code_unit', 'heading', 'cell'))
);
CREATE INDEX IF NOT EXISTS idx_segment_revision ON segment(revision_id);
CREATE INDEX IF NOT EXISTS idx_segment_type ON segment(segment_type);

CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5(
    text,
    content='segment',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 1'
);

CREATE TRIGGER IF NOT EXISTS segments_ai AFTER INSERT ON segment BEGIN
    INSERT INTO segments_fts(rowid, text) VALUES (new.rowid, new.text);
END;

CREATE TRIGGER IF NOT EXISTS segments_ad AFTER DELETE ON segment BEGIN
    INSERT INTO segments_fts(segments_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
END;

CREATE TRIGGER IF NOT EXISTS segments_au AFTER UPDATE ON segment BEGIN
    INSERT INTO segments_fts(segments_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
    INSERT INTO segments_fts(rowid, text) VALUES (new.rowid, new.text);
END;

-- ─────────────────────────────────────────────────────────────────────────────
-- Spatial index (RTree)
-- ─────────────────────────────────────────────────────────────────────────────

-- Spatial index (RTree).
-- The RTree first column is an integer rowid; entity TEXT ids are mapped via
-- spatial_entity so they survive the integer storage class of the virtual table.
CREATE TABLE IF NOT EXISTS spatial_entity (
    rowid     INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL UNIQUE
);

CREATE VIRTUAL TABLE IF NOT EXISTS spatial_index USING rtree(
    id,
    min_lat, max_lat,
    min_lon, max_lon
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Raster / vector / observations
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS raster_scene (
    id            TEXT PRIMARY KEY,
    revision_id   TEXT NOT NULL REFERENCES asset_revision(id) ON DELETE CASCADE,
    sensor        TEXT,
    bands         TEXT NOT NULL DEFAULT '[]',
    crs           TEXT NOT NULL,
    footprint     TEXT,
    bbox          TEXT NOT NULL DEFAULT '[]',
    acquired_at   TEXT,
    transform     TEXT,
    dtype         TEXT,
    nodata        REAL,
    width         INTEGER,
    height        INTEGER,
    resolution_m  REAL,
    metadata      TEXT DEFAULT '{}',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (crs LIKE 'EPSG:%')
);
CREATE INDEX IF NOT EXISTS idx_scene_revision ON raster_scene(revision_id);
CREATE INDEX IF NOT EXISTS idx_scene_sensor ON raster_scene(sensor);
CREATE INDEX IF NOT EXISTS idx_scene_acquired ON raster_scene(acquired_at);

CREATE TABLE IF NOT EXISTS raster_tile (
    id           TEXT PRIMARY KEY,
    scene_id     TEXT NOT NULL REFERENCES raster_scene(id) ON DELETE CASCADE,
    window       TEXT NOT NULL,
    transform    TEXT NOT NULL,
    footprint    TEXT,
    preview_path TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tile_scene ON raster_tile(scene_id);

CREATE TABLE IF NOT EXISTS vector_layer (
    id             TEXT PRIMARY KEY,
    revision_id    TEXT NOT NULL REFERENCES asset_revision(id) ON DELETE CASCADE,
    geometry_type  TEXT NOT NULL,
    crs            TEXT NOT NULL,
    footprint      TEXT,
    feature_count  INTEGER,
    metadata       TEXT DEFAULT '{}',
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (geometry_type IN ('Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon', 'GeometryCollection'))
);
CREATE INDEX IF NOT EXISTS idx_vector_revision ON vector_layer(revision_id);

CREATE TABLE IF NOT EXISTS observation (
    id           TEXT PRIMARY KEY,
    subject_id   TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    metric       TEXT NOT NULL,
    value        REAL NOT NULL,
    unit         TEXT,
    observed_at  TEXT NOT NULL,
    valid_from   TEXT,
    valid_to     TEXT,
    metadata     TEXT DEFAULT '{}',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_observation_subject ON observation(subject_id, subject_type);
CREATE INDEX IF NOT EXISTS idx_observation_metric ON observation(metric);
CREATE INDEX IF NOT EXISTS idx_observation_time ON observation(observed_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- Embeddings & relations
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS embedding_record (
    target_id   TEXT NOT NULL,
    target_type TEXT NOT NULL,
    space_id    TEXT NOT NULL,
    model_id    TEXT NOT NULL,
    dimension   INTEGER NOT NULL,
    checksum    TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (target_id, target_type, space_id)
);
CREATE INDEX IF NOT EXISTS idx_embedding_space ON embedding_record(space_id);
CREATE INDEX IF NOT EXISTS idx_embedding_model ON embedding_record(model_id);

CREATE TABLE IF NOT EXISTS relation (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL,
    predicate   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,
    extractor   TEXT DEFAULT 'manual',
    evidence_id TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    metadata    TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_relation_source ON relation(source_id);
CREATE INDEX IF NOT EXISTS idx_relation_target ON relation(target_id);
CREATE INDEX IF NOT EXISTS idx_relation_predicate ON relation(predicate);

-- ─────────────────────────────────────────────────────────────────────────────
-- Conversations, turns, retrieval, answers, citations
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS conversation (
    id               TEXT PRIMARY KEY,
    workspace_id     TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    collection_scope TEXT DEFAULT '[]',
    title            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    metadata         TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS turn (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    metadata        TEXT DEFAULT '{}',
    CHECK (role IN ('user', 'system', 'assistant'))
);
CREATE INDEX IF NOT EXISTS idx_turn_conversation ON turn(conversation_id);

CREATE TABLE IF NOT EXISTS retrieval_run (
    id          TEXT PRIMARY KEY,
    turn_id     TEXT REFERENCES turn(id),
    query       TEXT NOT NULL,
    query_plan  TEXT DEFAULT '{}',
    filters     TEXT DEFAULT '{}',
    config      TEXT DEFAULT '{}',
    candidates  TEXT NOT NULL DEFAULT '[]',
    results     TEXT NOT NULL DEFAULT '[]',
    latency_ms  INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_retrieval_run_turn ON retrieval_run(turn_id);

CREATE TABLE IF NOT EXISTS answer (
    id          TEXT PRIMARY KEY,
    turn_id     TEXT NOT NULL REFERENCES turn(id) ON DELETE CASCADE,
    model       TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    text        TEXT NOT NULL,
    abstained   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS citation (
    id          TEXT PRIMARY KEY,
    answer_id   TEXT NOT NULL REFERENCES answer(id) ON DELETE CASCADE,
    segment_id  TEXT NOT NULL REFERENCES segment(id),
    locator     TEXT NOT NULL DEFAULT '{}',
    claim_span  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_citation_answer ON citation(answer_id);
CREATE INDEX IF NOT EXISTS idx_citation_segment ON citation(segment_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- Feedback, datasets, jobs
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS feedback_event (
    id          TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    actor       TEXT DEFAULT 'user',
    label       TEXT NOT NULL,
    payload     TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    metadata    TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_feedback_target ON feedback_event(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback_event(created_at);

CREATE TABLE IF NOT EXISTS dataset_example (
    id                  TEXT PRIMARY KEY,
    task_type           TEXT NOT NULL,
    source_feedback_ids TEXT NOT NULL DEFAULT '[]',
    review_state        TEXT NOT NULL DEFAULT 'pending',
    reviewer_id         TEXT,
    reviewed_at         TEXT,
    version             INTEGER NOT NULL DEFAULT 1,
    dataset_card        TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (review_state IN ('pending', 'accepted', 'rejected'))
);
CREATE INDEX IF NOT EXISTS idx_dataset_example_state ON dataset_example(review_state);
CREATE INDEX IF NOT EXISTS idx_dataset_example_task ON dataset_example(task_type);

CREATE TABLE IF NOT EXISTS job (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    state       TEXT NOT NULL DEFAULT 'pending',
    progress    REAL DEFAULT 0.0,
    input       TEXT NOT NULL DEFAULT '{}',
    result      TEXT,
    error       TEXT,
    checkpoint  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (state IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
);
CREATE INDEX IF NOT EXISTS idx_job_state ON job(state);
CREATE INDEX IF NOT EXISTS idx_job_type ON job(type);

-- ─────────────────────────────────────────────────────────────────────────────
-- Migrations
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS schema_migration (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);