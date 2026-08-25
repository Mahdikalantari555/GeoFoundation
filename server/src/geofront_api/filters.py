from __future__ import annotations

from geomemory import GeoMemoryError, SearchFilters, SpatialFilter, TemporalFilter
from pydantic import ValidationError

from .errors import GeoFrontError
from .schemas import SpatialFilterRequest, TemporalFilterRequest


def _error_detail(exc: ValidationError) -> list[dict[str, object]]:
    """JSON-safe validation errors (raw ctx/input may carry exception objects)."""
    return [
        {"loc": e.get("loc", []), "msg": e.get("msg", ""), "type": e.get("type", "")}
        for e in exc.errors(include_url=False)
    ]


def build_spatial_filter(req: SpatialFilterRequest | None) -> SpatialFilter | None:
    """Convert a gateway request filter into the public lib model.

    Lib-side validation (bbox sanity, antimeridian, distance_lte pairing)
    maps to a 422 `invalid_spatial_filter` envelope.
    """
    if req is None:
        return None
    try:
        return SpatialFilter(
            op=req.op,
            geometry_id=req.geometry_id,
            bbox=req.bbox,
            distance_m=req.distance_m,
        )
    except ValidationError as exc:
        raise GeoFrontError(
            code="invalid_spatial_filter",
            message="Spatial filter is invalid.",
            status_code=422,
            detail=_error_detail(exc),
        ) from exc
    except GeoMemoryError as exc:  # SpatialValidationError from lib validators
        raise GeoFrontError(
            code="invalid_spatial_filter", message=str(exc), status_code=422
        ) from exc


def build_temporal_filter(req: TemporalFilterRequest | None) -> TemporalFilter | None:
    """Convert a gateway request filter into the public lib model."""
    if req is None:
        return None
    try:
        return TemporalFilter(field=req.field, **{"from": req.from_}, to=req.to)
    except ValidationError as exc:
        raise GeoFrontError(
            code="invalid_temporal_filter",
            message="Temporal filter is invalid.",
            status_code=422,
            detail=_error_detail(exc),
        ) from exc
    except GeoMemoryError as exc:
        raise GeoFrontError(
            code="invalid_temporal_filter", message=str(exc), status_code=422
        ) from exc


def build_search_filters(
    req: SpatialFilterRequest | None,
    temporal_req: TemporalFilterRequest | None,
    *,
    collections: list[str] | None = None,
    sensors: list[str] | None = None,
) -> SearchFilters | None:
    """Assemble a full SearchFilters for `ask` (None when no filter is set)."""
    spatial = build_spatial_filter(req)
    temporal = build_temporal_filter(temporal_req)
    if spatial is None and temporal is None and not collections and not sensors:
        return None
    return SearchFilters(
        collections=collections, sensors=sensors, spatial=spatial, temporal=temporal
    )
