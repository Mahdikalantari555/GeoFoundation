from __future__ import annotations

from fastapi import APIRouter

from . import __version__
from .schemas import HealthLLM, HealthResponse, HealthWorkspace
from .state import get_state

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    state = get_state()
    ws = HealthWorkspace(
        status="open" if state.is_open else "closed",
        path=str(state.workspace_path) if state.workspace_path else None,
        name=(
            state.workspace.settings.name if state.workspace is not None else None
        ),
    )
    return HealthResponse(
        version=__version__,
        workspace=ws,
        llm=HealthLLM(**state.llm_health()),  # type: ignore[arg-type]
    )
