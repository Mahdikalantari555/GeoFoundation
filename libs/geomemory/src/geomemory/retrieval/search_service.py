"""End-to-end search orchestration."""

from __future__ import annotations

import time
from typing import Any, Literal

from geomemory.core.models import (
    QueryPlan,
    RetrievalRun,
    SearchFilters,
    SearchHit,
    SearchRequest,
    SearchResult,
    SpatialFilter,
    TemporalFilter,
)
from geomemory.retrieval.deduplicator import deduplicate, enforce_diversity
from geomemory.retrieval.fusion import linear_fuse, rrf_fuse
from geomemory.retrieval.query_parser import QueryParser
from geomemory.retrieval.spatial_filter import apply_spatial_filter
from geomemory.retrieval.temporal_filter import apply_temporal_filter


class SearchService:
    """Orchestrate query → retrieve → fuse → dedup → return results.

    The service accepts one or more retrieval backends (sparse/dense) and
    combines their results using Reciprocal Rank Fusion by default.
    """

    def __init__(
        self,
        backends: list[Any],
        *,
        parser: QueryParser | None = None,
        max_per_document: int = 3,
    ) -> None:
        self.backends = backends
        self.parser = parser or QueryParser()
        self.max_per_document = max_per_document

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        top_k: int = 20,
        top_n: int = 5,
        filters: SearchFilters | None = None,
        modalities: Literal["text", "image", "both"] | None = None,
        modality_weight: float = 0.7,
    ) -> SearchResult:
        """Execute a hybrid search across the configured backends."""
        start = time.perf_counter()
        clean_query, filters = self.parser.parse(query, filters)
        intent = self.parser.detect_intent(clean_query)
        effective_modalities = modalities or "text"

        text_backends = [
            backend
            for backend in self.backends
            if not _is_image_backend(backend)
        ]
        image_backends = [
            backend
            for backend in self.backends
            if _is_image_backend(backend) and _image_backend_ready(backend)
        ]
        if effective_modalities == "text":
            active_backends = text_backends
        elif effective_modalities == "image":
            active_backends = image_backends
        else:
            active_backends = [*text_backends, *image_backends]

        plan = QueryPlan(
            intent=intent,
            mode=mode,
            spaces=[getattr(b, "space_id", "unknown") for b in active_backends],
            top_k=top_k,
            top_n=top_n,
            filters=filters,
            modalities=effective_modalities,
            modality_weight=modality_weight,
        )

        groups: list[list[SearchHit]] = []
        weights: list[float] = []
        for backend in active_backends:
            is_image = _is_image_backend(backend)
            request = SearchRequest(
                query=clean_query,
                filters=filters,
                top_k=top_k,
                top_n=top_n,
                mode=mode,
                modalities=effective_modalities,
                modality_weight=modality_weight,
            )
            hits = backend.search(request)
            if is_image:
                for hit in hits:
                    hit.metadata.setdefault("modality", "image")
            else:
                for hit in hits:
                    hit.metadata.setdefault("modality", "text")
            groups.append(hits)
            weights.append(modality_weight if is_image else 1.0)

        multimodal = effective_modalities == "both" and any(
            _is_image_backend(backend) for backend in active_backends
        )
        if multimodal and mode == "linear":
            fused = linear_fuse(groups, top_n=top_k, weights=weights)
        elif multimodal or mode == "hybrid":
            fused = rrf_fuse(groups, top_n=top_k, weights=weights)
        elif mode == "sparse":
            fused = groups[0] if groups else []
        elif mode == "dense":
            fused = groups[-1] if groups else []
        else:
            fused = linear_fuse(groups, top_n=top_k, weights=weights)

        fused = deduplicate(fused)
        fused = enforce_diversity(fused, max_per_document=self.max_per_document)
        fused = apply_hit_filters(
            fused, spatial=filters.spatial, temporal=filters.temporal, sensors=filters.sensors
        )
        fused = fused[:top_n]

        latency_ms = int((time.perf_counter() - start) * 1000)
        run = RetrievalRun(
            query=clean_query,
            query_plan=plan.model_dump(),
            filters=filters.model_dump(),
            config={
                "mode": mode,
                "top_k": top_k,
                "top_n": top_n,
                "fusion": "linear" if mode == "linear" and multimodal else "rrf",
                "modalities": effective_modalities,
                "modality_weight": modality_weight,
            },
            latency_ms=latency_ms,
        )

        return SearchResult(
            query=clean_query,
            query_plan=plan,
            hits=fused,
            total_hits=len(fused),
            latency_ms=latency_ms,
            retrieval_run_id=run.id,
        )


def _is_image_backend(backend: Any) -> bool:
    """Return whether a backend belongs to the isolated vision space."""
    return str(getattr(backend, "space_id", "")).startswith("image.")


def _image_backend_ready(backend: Any) -> bool:
    """Keep tiny image indexes out of multimodal fusion."""
    try:
        return int(backend.count()) >= 5
    except Exception:
        return False


def apply_hit_filters(
    hits: list[SearchHit],
    *,
    spatial: SpatialFilter | None = None,
    temporal: TemporalFilter | None = None,
    sensors: list[str] | None = None,
) -> list[SearchHit]:
    """Apply the canonical post-fusion filter chain: spatial → temporal → sensor."""
    hits = apply_spatial_filter(hits, spatial)
    hits = apply_temporal_filter(hits, temporal)
    if sensors:
        hits = [hit for hit in hits if hit_sensor(hit) is not None and hit_sensor(hit) in sensors]
    return hits


def hit_sensor(hit: SearchHit) -> str | None:
    """Return the sensor recorded on a hit, if any."""
    direct = hit.metadata.get("sensor")
    if direct:
        return str(direct)
    spatial = hit.metadata.get("spatial")
    if isinstance(spatial, dict):
        sensor = spatial.get("sensor")
        if sensor:
            return str(sensor)
    return None
