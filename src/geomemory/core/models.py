"""Pydantic domain models for all GeoMemory entities.

These models mirror the schema defined in ``.agent/spec/docs/Database Design.md``
and the data-model contracts in ``.agent/spec/docs/Component Design.md``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

from geomemory.core.exceptions import SpatialValidationError

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def utc_now() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    """Return a UUID4 string with an optional domain prefix."""
    return f"{prefix}_{uuid4().hex}"


def _json_dumps(value: Any) -> str:
    """Serialize a value to JSON with numpy and Path support."""
    return json.dumps(value, default=_json_default)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class GeoMemoryModel(BaseModel):
    """Base model with JSON helpers."""

    model_config = {"populate_by_name": True, "extra": "forbid"}

    def model_dump_json(self, **kwargs: Any) -> str:
        return json.dumps(self.model_dump(mode="json"), default=_json_default)


# ──────────────────────────────────────────────────────────────────────────────
# Filter models (public API)
# ──────────────────────────────────────────────────────────────────────────────


class SpatialFilter(GeoMemoryModel):
    """Spatial predicate filter.

    Exactly one of ``bbox`` or ``geometry_id`` should be provided.
    Coordinates are in EPSG:4326 (WGS84) lon/lat order.
    """

    op: Literal["intersects", "within", "contains", "distance_lte"] = "intersects"
    geometry_id: str | None = None
    bbox: tuple[float, float, float, float] | None = None  # (min_lon, min_lat, max_lon, max_lat)
    distance_m: float | None = None

    @model_validator(mode="after")
    def _validate(self) -> SpatialFilter:
        if self.bbox is None and self.geometry_id is None:
            raise ValueError("SpatialFilter requires either bbox or geometry_id")
        if self.bbox is not None:
            min_lon, min_lat, max_lon, max_lat = self.bbox
            if min_lon > max_lon or min_lat > max_lat:
                raise SpatialValidationError(
                    f"Invalid bbox — min values exceed max values: {self.bbox}"
                )
            if min_lon < -180 or max_lon > 180 or min_lat < -90 or max_lat > 90:
                raise SpatialValidationError(
                    f"Coordinate out of range — values must lie within WGS84 bounds: {self.bbox}"
                )
            if min_lon < -180 + 1 and max_lon > 180 - 1:
                raise SpatialValidationError(
                    "Antimeridian-crossing bboxes are not supported; split into two queries"
                )
        if self.op == "distance_lte" and self.distance_m is None:
            raise ValueError("distance_lte requires distance_m")
        return self

    @property
    def as_meta(self) -> dict[str, Any]:
        """Return a JSON-serializable filter dict for retrieval run logs."""
        return {"op": self.op, "geometry_id": self.geometry_id, "bbox": self.bbox, "distance_m": self.distance_m}


class TemporalFilter(GeoMemoryModel):
    """Temporal range filter over an explicit time field."""

    field: Literal["acquired_at", "observed_at", "published_at", "ingested_at"] = "observed_at"
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> TemporalFilter:
        if self.from_ is None and self.to is None:
            raise ValueError("TemporalFilter requires at least one of from_/to")
        if self.from_ is not None and self.to is not None and self.from_ > self.to:
            raise ValueError(f"TemporalFilter from ({self.from_}) exceeds to ({self.to})")
        return self

    @property
    def as_meta(self) -> dict[str, Any]:
        return {"field": self.field, "from": self.from_, "to": self.to}


class SearchFilters(GeoMemoryModel):
    """Full filter set applied at retrieval time."""

    collections: list[str] | None = None
    asset_types: list[str] | None = None  # document, code, raster, vector, table
    languages: list[str] | None = None  # e.g. en, fa
    sensors: list[str] | None = None  # e.g. Sentinel-2, Landsat-8
    spatial: SpatialFilter | None = None
    temporal: TemporalFilter | None = None
    taxonomy: list[str] | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Workspace & configuration
# ──────────────────────────────────────────────────────────────────────────────


class WorkspaceConfig(GeoMemoryModel):
    """Configuration for creating a new workspace."""

    name: str = "GeoMemory Workspace"
    language: Literal["en", "fa"] | None = None
    offline: bool = True
    model_path: str | None = Field(default=None, description="Path to LLM GGUF model")
    embedding_path: str | None = Field(default=None, description="Path to embedding GGUF model")
    vision_path: str | None = Field(default=None, description="Path to vision GGUF model (optional)")
    default_collection: str | None = Field(
        default=None, description="Name of collection created automatically on open"
    )


class WorkspaceSettings(GeoMemoryModel):
    """Persisted settings stored in workspace.yaml."""

    name: str
    language: Literal["en", "fa"] | None = None
    offline: bool = True
    model_path: str | None = None
    embedding_path: str | None = None
    vision_path: str | None = None
    default_collection: str | None = None
    index_dir: str = "indexes"
    objects_dir: str = "objects"
    logs_dir: str = "logs"
    batch_size: int = 64
    thread_count: int = 4


# ──────────────────────────────────────────────────────────────────────────────
# Core entities
# ──────────────────────────────────────────────────────────────────────────────


class Workspace(GeoMemoryModel):
    """Top-level container for all data, settings, and storage paths."""

    id: str = Field(default_factory=lambda: new_id("ws"))
    name: str
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class Collection(GeoMemoryModel):
    """Logical grouping of assets within a workspace."""

    id: str = Field(default_factory=lambda: new_id("col"))
    workspace_id: str
    name: str
    description: str = ""
    created_at: str = Field(default_factory=utc_now)
    archived: bool = False


class Asset(GeoMemoryModel):
    """Stable identity for a source resource."""

    id: str = Field(default_factory=lambda: new_id("ast"))
    collection_id: str
    kind: Literal["document", "code", "raster", "vector", "table"]
    title: str | None = None
    current_revision_id: str | None = None
    created_at: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    deleted_at: str | None = None


class AssetRevision(GeoMemoryModel):
    """Immutable version of raw content with hash and parser metadata."""

    id: str = Field(default_factory=lambda: new_id("rev"))
    asset_id: str
    hash: str
    mime_type: str
    size_bytes: int = 0
    parser_version: str = "0.1.0"
    ingested_at: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("hash")
    @classmethod
    def _validate_hash(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError(f"hash must be a 64-char hex SHA-256 digest, got {v!r}")
        return v.lower()


class Segment(GeoMemoryModel):
    """Chunk of parsed document text with locator and type."""

    id: str = Field(default_factory=lambda: new_id("seg"))
    revision_id: str
    segment_type: Literal[
        "paragraph", "table", "formula", "code_unit", "heading", "cell"
    ] = "paragraph"
    text: str
    locator: dict[str, Any] = Field(default_factory=dict)
    parent_section_id: str | None = None
    neighbor_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class RasterScene(GeoMemoryModel):
    """Geospatial scene extracted from a raster file."""

    id: str = Field(default_factory=lambda: new_id("scn"))
    revision_id: str
    sensor: str | None = None
    bands: list[dict[str, Any]] = Field(default_factory=list)
    crs: str = "EPSG:4326"
    footprint: str | None = None  # WKB hex
    bbox: list[float] = Field(default_factory=list)  # [min_lon, min_lat, max_lon, max_lat]
    acquired_at: str | None = None
    transform: list[float] = Field(default_factory=list)
    dtype: str | None = None
    nodata: float | None = None
    width: int | None = None
    height: int | None = None
    resolution_m: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)

    @field_validator("crs")
    @classmethod
    def _validate_crs(cls, v: str) -> str:
        if not v.upper().startswith("EPSG:"):
            raise ValueError(f"crs must start with EPSG:, got {v!r}")
        return v.upper()

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, v: list[float]) -> list[float]:
        if v and len(v) != 4:
            raise ValueError(f"bbox must have exactly 4 values, got {len(v)}")
        return v


class RasterTile(GeoMemoryModel):
    """Windowed subset of a raster scene with transform."""

    id: str = Field(default_factory=lambda: new_id("tile"))
    scene_id: str
    window: dict[str, int] = Field(default_factory=dict)  # x, y, width, height
    transform: list[float] = Field(default_factory=list)
    footprint: str | None = None
    preview_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class VectorLayer(GeoMemoryModel):
    """Vector data layer extracted from GeoJSON/GeoPackage."""

    id: str = Field(default_factory=lambda: new_id("vec"))
    revision_id: str
    geometry_type: Literal[
        "Point",
        "LineString",
        "Polygon",
        "MultiPoint",
        "MultiLineString",
        "MultiPolygon",
        "GeometryCollection",
    ]
    crs: str = "EPSG:4326"
    footprint: str | None = None
    feature_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class Observation(GeoMemoryModel):
    """Temporal or computed measurement tied to a subject."""

    id: str = Field(default_factory=lambda: new_id("obs"))
    subject_id: str
    subject_type: str  # raster_scene, asset, etc.
    metric: str
    value: float
    unit: str | None = None
    observed_at: str = Field(default_factory=utc_now)
    valid_from: str | None = None
    valid_to: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class EmbeddingRecord(GeoMemoryModel):
    """Link between a target entity and its vector in a specific embedding space."""

    target_id: str
    target_type: str  # segment, raster_tile, observation
    space_id: str  # text.nomic.v1, image.olmoearth.v1
    model_id: str
    dimension: int
    checksum: str  # SHA-256 of the embedding vector bytes
    created_at: str = Field(default_factory=utc_now)

    @field_validator("checksum")
    @classmethod
    def _validate_checksum(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower()):
            raise ValueError(f"checksum must be a 64-char hex SHA-256 digest, got {v!r}")
        return v.lower()

    @classmethod
    def from_vector(
        cls,
        target_id: str,
        target_type: str,
        space_id: str,
        model_id: str,
        vector: np.ndarray,
    ) -> EmbeddingRecord:
        """Build an EmbeddingRecord from a numpy vector, computing its checksum."""
        raw = np.ascontiguousarray(vector, dtype=np.float32).tobytes()
        checksum = hashlib.sha256(raw).hexdigest()
        return cls(
            target_id=target_id,
            target_type=target_type,
            space_id=space_id,
            model_id=model_id,
            dimension=int(vector.shape[0]),
            checksum=checksum,
        )


class Relation(GeoMemoryModel):
    """Explicit typed relationship between two entities with evidence."""

    id: str = Field(default_factory=lambda: new_id("rel"))
    source_id: str
    predicate: str
    target_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extractor: str = "manual"
    evidence_id: str | None = None
    created_at: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Conversation, retrieval, QA entities
# ──────────────────────────────────────────────────────────────────────────────


class Conversation(GeoMemoryModel):
    """Chat session within a workspace."""

    id: str = Field(default_factory=lambda: new_id("conv"))
    workspace_id: str
    collection_scope: list[str] = Field(default_factory=list)
    title: str | None = None
    created_at: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Turn(GeoMemoryModel):
    """Single message in a conversation."""

    id: str = Field(default_factory=lambda: new_id("turn"))
    conversation_id: str
    role: Literal["user", "system", "assistant"]
    content: str
    created_at: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalRun(GeoMemoryModel):
    """Complete trace of a retrieval operation."""

    id: str = Field(default_factory=lambda: new_id("run"))
    turn_id: str | None = None
    query: str
    query_plan: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int | None = None
    created_at: str = Field(default_factory=utc_now)


class Answer(GeoMemoryModel):
    """LLM-generated answer to a question."""

    id: str = Field(default_factory=lambda: new_id("ans"))
    turn_id: str | None = None
    model: str
    prompt_hash: str
    text: str
    abstained: bool = False
    created_at: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(GeoMemoryModel):
    """Link from an answer claim to a specific source segment."""

    id: str = Field(default_factory=lambda: new_id("cit"))
    answer_id: str
    segment_id: str
    locator: dict[str, Any] = Field(default_factory=dict)
    claim_span: dict[str, int] | None = None
    created_at: str = Field(default_factory=utc_now)


# ──────────────────────────────────────────────────────────────────────────────
# Search results (public API)
# ──────────────────────────────────────────────────────────────────────────────


class SearchHit(GeoMemoryModel):
    """A single ranked hit with score components."""

    id: str
    score: float = 0.0
    sparse_score: float | None = None
    dense_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    text: str = ""
    locator: dict[str, Any] = Field(default_factory=dict)


class QueryPlan(GeoMemoryModel):
    """Description of how a query was routed and executed."""

    intent: str = "search"  # search, grounded_qa, research, code, image_search
    mode: str = "hybrid"  # sparse, dense, hybrid
    spaces: list[str] = Field(default_factory=list)
    top_k: int = 20
    top_n: int = 5
    filters: SearchFilters | None = None


class SearchResult(GeoMemoryModel):
    """Result of a hybrid search."""

    query: str
    query_plan: QueryPlan
    hits: list[SearchHit] = Field(default_factory=list)
    total_hits: int = 0
    latency_ms: int | None = None
    retrieval_run_id: str | None = None


class QAResult(GeoMemoryModel):
    """Public result of a grounded QA call."""

    text: str
    citations: list[Citation] = Field(default_factory=list)
    abstained: bool = False
    abstention_reason: str | None = None
    sources: list[SearchHit] = Field(default_factory=list)
    retrieval_run_id: str | None = None
    latency_ms: int | None = None
    model: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# Feedback & evaluation
# ──────────────────────────────────────────────────────────────────────────────


class FeedbackEvent(GeoMemoryModel):
    """Immutable raw feedback record."""

    id: str = Field(default_factory=lambda: new_id("fb"))
    target_type: str  # answer, retrieval_run, segment, citation
    target_id: str
    actor: str = "user"
    label: str  # answer_rating, source_relevance, edited_answer, ...
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetExample(GeoMemoryModel):
    """A reviewed/exportable example derived from feedback events."""

    id: str = Field(default_factory=lambda: new_id("dsx"))
    task_type: str  # rag_eval, qa_eval, sft, preference, tool_eval
    source_feedback_ids: list[str] = Field(default_factory=list)
    review_state: Literal["pending", "accepted", "rejected"] = "pending"
    reviewer_id: str | None = None
    reviewed_at: str | None = None
    version: int = 1
    dataset_card: dict[str, Any] | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class Job(GeoMemoryModel):
    """Background ingestion, indexing, or evaluation job."""

    id: str = Field(default_factory=lambda: new_id("job"))
    type: str  # ingestion, indexing, evaluation, export
    state: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    input: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    checkpoint: dict[str, Any] | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


# ──────────────────────────────────────────────────────────────────────────────
# Ingestion data models (internal pipeline contracts)
# ──────────────────────────────────────────────────────────────────────────────


class SourceRef(GeoMemoryModel):
    """Reference to a source: path, url, or raw bytes."""

    path: str | None = None
    url: str | None = None
    git_ref: str | None = None
    content_bytes: bytes | None = None

    @model_validator(mode="after")
    def _validate(self) -> SourceRef:
        provided = sum(x is not None for x in (self.path, self.url, self.content_bytes))
        if provided != 1:
            raise ValueError("SourceRef requires exactly one of path, url, or content_bytes")
        return self


class ParsedObject(GeoMemoryModel):
    """Structured output of a loader."""

    source: SourceRef
    mime_type: str
    title: str
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw: Any = None


class SegmentDraft(GeoMemoryModel):
    """Chunker output before persistence."""

    text: str
    segment_type: Literal[
        "paragraph", "table", "formula", "code_unit", "heading", "cell"
    ] = "paragraph"
    locator: dict[str, Any] = Field(default_factory=dict)
    parent_section_id: str | None = None
    neighbor_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexRecord(GeoMemoryModel):
    """Record upserted into a retrieval backend."""

    id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: Any = None  # np.ndarray | None (kept as Any for JSON serialization)
    space_id: str = "text.nomic.v1"


class SearchRequest(GeoMemoryModel):
    """Internal retrieval request passed to a RetrievalBackend."""

    query: str
    query_embedding: Any = None  # np.ndarray | None
    filters: SearchFilters = Field(default_factory=SearchFilters)
    top_k: int = 20
    top_n: int = 5
    mode: Literal["sparse", "dense", "hybrid"] = "hybrid"
    fusion: Literal["rrf", "linear"] = "rrf"


class GenerationRequest(GeoMemoryModel):
    """Request payload for an LLM backend."""

    prompt: str
    context: list[SearchHit] = Field(default_factory=list)
    max_tokens: int = 512
    temperature: float = 0.2
    stop_sequences: list[str] = Field(default_factory=list)


class GenerationResult(GeoMemoryModel):
    """Result from an LLM backend."""

    text: str
    prompt_hash: str
    model_id: str
    tokens_used: int = 0
    latency_ms: int = 0
    abstained: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Index manifest
# ──────────────────────────────────────────────────────────────────────────────


class IndexManifest(GeoMemoryModel):
    """Metadata describing a retrieval index."""

    space_id: str
    model_id: str
    model_revision: str = ""
    dimension: int
    normalization: str = "l2"
    chunker: str = "header_then_token"
    chunk_size: int = 1000
    chunk_overlap: int = 150
    created_at: str = Field(default_factory=utc_now)
    doc_count: int = 0

    def to_json(self) -> str:
        return _json_dumps(self.model_dump(mode="json"))


class AssetDetail(GeoMemoryModel):
    """Full inspection view of an asset."""

    asset: Asset
    revision: AssetRevision | None = None
    collections: list[Collection] = Field(default_factory=list)
    segments: list[Segment] = Field(default_factory=list)
    scenes: list[RasterScene] = Field(default_factory=list)
    layers: list[VectorLayer] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    embeddings: list[EmbeddingRecord] = Field(default_factory=list)


class BenchmarkConfig(GeoMemoryModel):
    """Configuration for a benchmark run."""

    seeds: list[int] = Field(default_factory=lambda: [42])
    top_k_values: list[int] = Field(default_factory=lambda: [5, 10, 20])
    mode: Literal["sparse", "dense", "hybrid", "hybrid_rerank"] = "hybrid"
    output_dir: str | None = None


class BenchmarkResult(GeoMemoryModel):
    """Aggregated benchmark results."""

    name: str = "benchmark"
    metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    report: str = ""
    config: BenchmarkConfig = Field(default_factory=BenchmarkConfig)
    created_at: str = Field(default_factory=utc_now)