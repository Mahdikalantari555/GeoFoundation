"""Vision embedder selection factory."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from geomemory.embeddings.vision_embedder import PlaceholderVisionEmbedder, VisionEmbedder

if TYPE_CHECKING:
    from geomemory.core.models import WorkspaceSettings


def build_vision_embedder(settings: WorkspaceSettings) -> VisionEmbedder:
    """Return a vision embedder based on workspace settings.

    - If ``vision_path`` is set and ``torch`` is importable, returns an
      :class:`OlmoEarthVisionEmbedder`.
    - Otherwise, returns :class:`PlaceholderVisionEmbedder`.
    """
    vision_path = settings.vision_path
    if vision_path is None:
        return PlaceholderVisionEmbedder()

    try:
        importlib.import_module("torch")
    except ImportError:
        return PlaceholderVisionEmbedder()

    from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

    return OlmoEarthVisionEmbedder(vision_path)
