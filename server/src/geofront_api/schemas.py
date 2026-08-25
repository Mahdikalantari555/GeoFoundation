from __future__ import annotations

from typing import Any

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
