from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import WorkspaceNotOpenError

if TYPE_CHECKING:
    from geomemory import GeoMemory


@dataclass
class AppState:
    """Holds the single active workspace and the platform write lock.

    Invariants (AGENTS.md): one uvicorn worker, one active workspace,
    all write operations serialized behind `write_lock`. Blocking facade
    calls must be dispatched to a threadpool, never run on the loop.
    """

    workspace: GeoMemory | None = None
    workspace_path: Path | None = None
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def require_workspace(self) -> GeoMemory:
        if self.workspace is None:
            raise WorkspaceNotOpenError()
        return self.workspace

    @property
    def is_open(self) -> bool:
        return self.workspace is not None

    async def close(self) -> None:
        """Close the active workspace (acquires the write lock)."""
        async with self.write_lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        """Close the active workspace. Caller must hold the write lock."""
        ws = self.workspace
        if ws is None:
            return
        await asyncio.to_thread(ws.close)
        self.workspace = None
        self.workspace_path = None

    def llm_health(self) -> dict[str, object]:
        settings = self.workspace.settings if self.workspace is not None else None
        provider = getattr(settings, "llm_provider", None) or "api"
        key_env = getattr(settings, "llm_api_key_env", None) or "GEOMEMORY_LLM_API_KEY"
        base_url = getattr(settings, "llm_api_base_url", None)
        return {
            "provider": provider,
            "key_env": key_env,
            "key_configured": bool(os.environ.get(key_env, "")),
            "base_url": base_url,
        }


_state: AppState | None = None


def get_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state


def reset_state() -> None:
    global _state
    _state = AppState()
