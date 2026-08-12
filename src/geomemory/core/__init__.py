"""Core domain: models, workspace, events, plugins, exceptions."""

from __future__ import annotations

from geomemory.core.config import default_settings, load_settings, save_settings
from geomemory.core.events import DomainEvent, EventBus
from geomemory.core.exceptions import GeoMemoryError
from geomemory.core.hashing import hash_object_path, sha256_bytes, sha256_file
from geomemory.core.models import GeoMemoryModel
from geomemory.core.plugin_registry import (
    BackendRegistry,
    ChunkerRegistry,
    EmbedderRegistry,
    LoaderRegistry,
)
from geomemory.core.workspace import GeoMemory

__all__ = [
    "BackendRegistry",
    "ChunkerRegistry",
    "DomainEvent",
    "EmbedderRegistry",
    "EventBus",
    "GeoMemory",
    "GeoMemoryError",
    "GeoMemoryModel",
    "LoaderRegistry",
    "default_settings",
    "hash_object_path",
    "load_settings",
    "save_settings",
    "sha256_bytes",
    "sha256_file",
]