"""GeoAgent — lightweight agent framework over the GeoMemory public API."""

from geoagent.config import AgentSettings, load_settings
from geoagent.registry import (
    ArtifactRef,
    Registry,
    RunContext,
    ToolDefinition,
    ToolResult,
)

__version__ = "0.1.0"

__all__ = [
    "AgentSettings",
    "ArtifactRef",
    "Registry",
    "RunContext",
    "ToolDefinition",
    "ToolResult",
    "__version__",
    "load_settings",
]
