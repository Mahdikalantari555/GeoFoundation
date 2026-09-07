from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("geofront.errors")


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if isinstance(rid, str) and rid:
        return rid
    # Fallback for handlers invoked without middleware (e.g. direct test calls)
    header = request.headers.get("x-request-id")
    if header:
        return header
    return uuid.uuid4().hex[:12]


class GeoFrontError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        detail: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail


class WorkspaceNotOpenError(GeoFrontError):
    def __init__(self) -> None:
        super().__init__(
            code="workspace_not_open",
            message="No workspace is open. Create or open a workspace first.",
            status_code=409,
        )


def _envelope(code: str, message: str, detail: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        body["detail"] = detail
    return {"error": body}


async def geofront_error_handler(request: Request, exc: GeoFrontError) -> JSONResponse:
    rid = _request_id(request)
    resp = JSONResponse(
        status_code=exc.status_code,
        content=_envelope(exc.code, exc.message, exc.detail),
        headers={"X-Request-ID": rid},
    )
    return resp


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    rid = _request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope("http_error", str(exc.detail), None),
        headers={"X-Request-ID": rid},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    rid = _request_id(request)
    return JSONResponse(
        status_code=422,
        content=_envelope("validation", "Request validation failed.", exc.errors()),
        headers={"X-Request-ID": rid},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = _request_id(request)
    log.exception("unhandled exception request_id=%s %s %s", rid, request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_envelope("internal_error", "Unexpected server error.", {"request_id": rid}),
        headers={"X-Request-ID": rid},
    )
