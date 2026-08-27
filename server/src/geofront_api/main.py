from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

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

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    import asyncio

    get_event_bus().bind(asyncio.get_running_loop())
    yield
    from .jobs import get_job_manager
    from .state import get_state

    await get_job_manager().aclose()
    await get_state().close()


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

    app.add_exception_handler(GeoFrontError, geofront_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    return app


app = create_app()
