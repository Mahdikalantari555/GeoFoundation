"""Temporal filtering over search hits."""

from __future__ import annotations

from geomemory.core.models import SearchHit, TemporalFilter


def apply_temporal_filter(hits: list[SearchHit], temporal: TemporalFilter | None) -> list[SearchHit]:
    """Keep hits whose timestamp for ``temporal.field`` falls in the requested range."""
    if temporal is None:
        return hits
    return [hit for hit in hits if _hit_in_range(hit, temporal)]


def _hit_in_range(hit: SearchHit, temporal: TemporalFilter) -> bool:
    value = _field_value(hit, temporal.field)
    if value is None:
        return False
    return time_in_range(value, temporal.from_, temporal.to)


def _field_value(hit: SearchHit, field: str) -> str | None:
    """Resolve the timestamp value for a temporal field from hit metadata."""
    if field == "acquired_at":
        return hit.metadata.get("spatial", {}).get("acquired_at")
    if field == "observed_at":
        observation = hit.metadata.get("observation")
        if isinstance(observation, dict):
            return observation.get("observed_at")
        return None
    if field in ("published_at", "ingested_at"):
        return hit.metadata.get(field)
    return hit.metadata.get(field)


def time_in_range(value: str | None, from_: str | None, to: str | None) -> bool:
    """Return True if an ISO timestamp falls within [from_, to] (ISO string compare)."""
    if value is None:
        return False
    if from_ is not None and value < from_:
        return False
    if to is not None and value > to:
        return False
    return True
