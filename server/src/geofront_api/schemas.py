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
