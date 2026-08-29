from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

try:
    from dotenv import load_dotenv

    # Load .env (and GEOMEMORY_LLM_API_KEY) for local dev. Missing dotenv or
    # file is non-fatal — production injects env vars directly.
    load_dotenv()
except Exception as exc:  # noqa: BLE001 - optional dependency / missing file
    logging.getLogger("geofront").debug("dotenv load skipped: %s", exc)

from . import __version__
from .errors import (
    GeoFrontError,
    geofront_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from .events import get_event_bus
from .health import router as health_router
from .routers.agent.chat import router as agent_chat_router
from .routers.agent.conversations import router as agent_conversations_router
from .routers.agent.farms import router as agent_farms_router
from .routers.agent.files import router as agent_files_router
from .routers.agent.maps import router as agent_maps_router
from .routers.agent.playbooks import router as agent_playbooks_router
from .routers.agent.tools import router as agent_tools_router
from .routers.ask import router as ask_router
from .routers.collections import router as collections_router
from .routers.doctor import router as doctor_router
from .routers.eval import router as eval_router
from .routers.events import router as events_router
from .routers.feedback import router as feedback_router
from .routers.index import router as index_router
from .routers.ingest import router as ingest_router
from .routers.jobs import router as jobs_router
from .routers.search import router as search_router
from .routers.workspace import router as workspace_router

API_PREFIX = "/api/v1"

log = logging.getLogger("geofront")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
)

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    import asyncio

    get_event_bus().bind(asyncio.get_running_loop())
    log.info("GeoFoundation gateway starting up (api_prefix=%s)", API_PREFIX)
    log.info("GeoFoundation gateway ready")
    yield
    from .jobs import get_job_manager
    from .services.agent import reset_agent_service
    from .state import get_state

    await get_job_manager().aclose()
    await get_state().close()
    reset_agent_service()


def create_app() -> FastAPI:
    app = FastAPI(
        title="GeoFoundation Gateway",
        version=__version__,
        description=(
            "Data-sovereign AI platform for remote sensing research. "
            "HTTP facade over the geomemory and geoagent public APIs."
        ),
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(workspace_router, prefix=API_PREFIX)
    app.include_router(collections_router, prefix=API_PREFIX)
    app.include_router(ingest_router, prefix=API_PREFIX)
    app.include_router(jobs_router, prefix=API_PREFIX)
    app.include_router(search_router, prefix=API_PREFIX)
    app.include_router(ask_router, prefix=API_PREFIX)
    app.include_router(feedback_router, prefix=API_PREFIX)
    app.include_router(index_router, prefix=API_PREFIX)
    app.include_router(eval_router, prefix=API_PREFIX)
    app.include_router(doctor_router, prefix=API_PREFIX)
    app.include_router(events_router, prefix=API_PREFIX)
    app.include_router(agent_chat_router, prefix=API_PREFIX)
    app.include_router(agent_conversations_router, prefix=API_PREFIX)
    app.include_router(agent_tools_router, prefix=API_PREFIX)
    app.include_router(agent_playbooks_router, prefix=API_PREFIX)
    app.include_router(agent_files_router, prefix=API_PREFIX)
    app.include_router(agent_farms_router, prefix=API_PREFIX)
    app.include_router(agent_maps_router, prefix=API_PREFIX)

    app.add_exception_handler(GeoFrontError, geofront_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    return app


app = create_app()
