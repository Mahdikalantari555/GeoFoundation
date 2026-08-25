from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: Any | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class HealthWorkspace(BaseModel):
    status: str = Field(examples=["closed", "open"])
    path: str | None = None
    name: str | None = None


class HealthLLM(BaseModel):
    provider: str
    key_env: str
    key_configured: bool
    base_url: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    workspace: HealthWorkspace
    llm: HealthLLM


class CreateCollectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class IngestBytesRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    data_base64: str = Field(min_length=1)
    collection_id: str
    index_after: bool = True
    parser: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Workspace


class CreateWorkspaceRequest(BaseModel):
    path: str
    name: str = "GeoMemory Workspace"
    language: str | None = Field(default=None, pattern="^(en|fa)$")
    offline: bool = True
    model_path: str | None = None
    embedding_path: str | None = None
    vision_path: str | None = None
    default_collection: str | None = None


class OpenWorkspaceRequest(BaseModel):
    path: str


class UpdateSettingsRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = None
    language: str | None = Field(default=None, pattern="^(en|fa)$")
    offline: bool | None = None
    model_path: str | None = None
    embedding_path: str | None = None
    vision_path: str | None = None
    default_collection: str | None = None
    batch_size: int | None = Field(default=None, ge=1, le=1024)
    thread_count: int | None = Field(default=None, ge=1, le=128)
    llm_provider: str | None = Field(default=None, pattern="^(api|llamacpp)$")
    llm_api_base_url: str | None = None
    llm_api_key_env: str | None = None
    llm_model_id: str | None = None
    llm_context_window: int | None = Field(default=None, ge=1024, le=200000)
    embedding_backend: str | None = Field(
        default=None, pattern="^(hashing|llama-cpp|sentence-transformers)$"
    )
    st_model_name: str | None = None
    vector_backend: str | None = Field(default=None, pattern="^(local|qdrant)$")
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    pdf_parser: str | None = Field(default=None, pattern="^(auto|opendataloader|pymupdf)$")


# ──────────────────────────────────────────────────────────────────────────────
# Search / Ask / Feedback


class SpatialFilterRequest(BaseModel):
    """BBox or geometry reference; mirrors the lib SpatialFilter contract."""

    model_config = {"extra": "forbid"}

    op: Literal["intersects", "within", "contains", "distance_lte"] = "intersects"
    geometry_id: str | None = None
    bbox: tuple[float, float, float, float] | None = None  # min_lon, min_lat, max_lon, max_lat
    distance_m: float | None = Field(default=None, ge=0)


class TemporalFilterRequest(BaseModel):
    """Range filter over an explicit time field (`from`/`to` as ISO date strings)."""

    model_config = {"extra": "forbid"}

    field: Literal["acquired_at", "observed_at", "published_at", "ingested_at"] = "observed_at"
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None


class SearchRequest(BaseModel):
    model_config = {"extra": "forbid"}

    query: str = Field(min_length=1, max_length=2000)
    mode: Literal["sparse", "dense", "hybrid"] = "hybrid"
    top_k: int = Field(default=20, ge=1, le=500)
    top_n: int = Field(default=5, ge=1, le=100)
    collections: list[str] | None = None
    sensor: list[str] | None = None
    spatial: SpatialFilterRequest | None = None
    temporal: TemporalFilterRequest | None = None


class AskRequest(BaseModel):
    model_config = {"extra": "forbid"}

    question: str = Field(min_length=1, max_length=4000)
    mode: Literal["grounded_qa", "research", "code"] = "grounded_qa"
    collections: list[str] | None = None
    sensor: list[str] | None = None
    spatial: SpatialFilterRequest | None = None
    temporal: TemporalFilterRequest | None = None


class FeedbackRequest(BaseModel):
    """Immutable feedback event (answer rating, source relevance, …)."""

    model_config = {"extra": "forbid"}

    target_type: Literal["answer", "retrieval_run", "segment", "citation"]
    target_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=100)
    actor: str = Field(default="user", max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
