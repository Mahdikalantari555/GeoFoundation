"""Agent service: manages the GeoAgent core lifecycle.

One agent instance per active workspace. The service lazily initializes
the agent when a workspace is open and provides access to the registry,
store, and core.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from geoagent.agent import AgentCore, build_backend
from geoagent.config import AgentSettings
from geoagent.registry import Registry
from geoagent.store import Store
from geoagent.tools import advisor_tools, cli_runner, gis_tools, memory_tools

from ..errors import GeoFrontError


class AgentService:
    """Manages the GeoAgent core for the active workspace.

    Lazily initializes the agent on first use. The agent's workspace
    is set to a subdirectory of the GeoMemory workspace.
    """

    def __init__(self) -> None:
        self._core: AgentCore | None = None
        self._registry: Registry | None = None
        self._store: Store | None = None
        self._settings: Any | None = None  # type: ignore[no-redef]
        self._lock = asyncio.Lock()

    @property
    def is_initialized(self) -> bool:
        return self._core is not None

    @property
    def registry(self) -> Registry:
        if self._registry is None:
            raise GeoFrontError(
                code="agent_not_ready",
                message="Agent not initialized. Open a workspace first.",
                status_code=409,
            )
        return self._registry

    @property
    def store(self) -> Store:
        if self._store is None:
            raise GeoFrontError(
                code="agent_not_ready",
                message="Agent not initialized. Open a workspace first.",
                status_code=409,
            )
        return self._store

    @property
    def core(self) -> AgentCore:
        if self._core is None:
            raise GeoFrontError(
                code="agent_not_ready",
                message="Agent not initialized. Open a workspace first.",
                status_code=409,
            )
        return self._core

    def init(self, workspace_path: Path) -> None:
        """Initialize the agent for the given workspace path."""
        agent_workspace = workspace_path / "geoagent"
        agent_workspace.mkdir(parents=True, exist_ok=True)

        settings = AgentSettings(
            workspace=agent_workspace,
            memory_workspace=str(workspace_path),
        )

        store = Store(agent_workspace / "agent.db")
        registry = self._build_registry(settings, store)
        try:
            backend = build_backend(settings)
        except Exception:  # noqa: BLE001 — LLM key missing → abstention backend
            from geoagent.llm.base import ChatResponse

            class _AbstainBackend:  # type: ignore[no-redef]
                def chat(self, messages, tools=None):  # type: ignore[no-untyped-def]
                    return ChatResponse(
                        content="LLM unavailable — no API key configured. Configure the key on the server and retry."
                    )

            backend = _AbstainBackend()  # type: ignore[assignment]

        core = AgentCore(settings, backend, registry, store)
        self._settings = settings
        self._registry = registry
        self._store = store
        self._core = core

    def _build_registry(self, settings: AgentSettings, store: Store) -> Registry:
        registry = Registry()
        memory_tools.register(registry)
        gis_tools.register(registry)
        advisor_tools.register(registry)
        cli_runner.register_from_config(registry, settings)
        return registry

    def reset(self) -> None:
        """Reset the agent (e.g., when workspace closes)."""
        if self._store is not None:
            self._store.close()
        self._core = None
        self._registry = None
        self._store = None
        self._settings = None


_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


def reset_agent_service() -> None:
    global _agent_service
    if _agent_service is not None:
        _agent_service.reset()
    _agent_service = None
