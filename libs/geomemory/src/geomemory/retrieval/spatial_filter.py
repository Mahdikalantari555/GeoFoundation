"""Spatial filtering over search hits and RTree pre-filtering."""

from __future__ import annotations

import math
import sqlite3

from geomemory.core.models import SearchHit, SpatialFilter
from geomemory.storage.repositories.spatial_repo import SpatialRepository

_METERS_PER_DEGREE = 111320.0


def apply_spatial_filter(hits: list[SearchHit], spatial: SpatialFilter | None) -> list[SearchHit]:
    """Keep hits whose segment ``metadata[\"spatial\"][\"bbox\"]`` satisfies the filter."""
    if spatial is None:
        return hits
    return [hit for hit in hits if _hit_passes(hit, spatial)]


def spatial_ids(conn: sqlite3.Connection, spatial: SpatialFilter | None) -> list[str]:
    """Return entity ids whose RTree entry satisfies the filter (pre-filter)."""
    if spatial is None or spatial.bbox is None:
        return []
    repo = SpatialRepository(conn)
    if spatial.op == "intersects":
        return repo.intersects(spatial.bbox)
    if spatial.op == "within":
        return repo.within(spatial.bbox)
    if spatial.op == "contains":
        return repo.contains(spatial.bbox)
    if spatial.op == "distance_lte":
        return repo.intersects(_expanded_bbox(spatial.bbox, spatial.distance_m or 0.0))
    return []


def _hit_passes(hit: SearchHit, spatial: SpatialFilter) -> bool:
    bbox = hit.metadata.get("spatial", {}).get("bbox")
    if not bbox or len(bbox) != 4:
        return False
    return _bbox_predicate(spatial, bbox)


def _bbox_predicate(spatial: SpatialFilter, hit_bbox: list[float]) -> bool:
    query = spatial.bbox
    if query is None:
        return False
    if spatial.op == "intersects":
        return _intersects(query, hit_bbox)
    if spatial.op == "within":
        return _within(query, hit_bbox)
    if spatial.op == "contains":
        return _within(hit_bbox, query)
    if spatial.op == "distance_lte":
        return _distance_lte(query, hit_bbox, spatial.distance_m or 0.0)
    return False


def _intersects(query: tuple[float, float, float, float], hit: list[float]) -> bool:
    return not (query[2] < hit[0] or query[0] > hit[2] or query[3] < hit[1] or query[1] > hit[3])


def _within(outer: tuple[float, float, float, float], inner: list[float]) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def _distance_lte(query: tuple[float, float, float, float], hit: list[float], distance_m: float) -> bool:
    """Approximate distance check between bbox centers using haversine."""
    q_lat = (query[1] + query[3]) / 2.0
    q_lon = (query[0] + query[2]) / 2.0
    h_lat = (hit[1] + hit[3]) / 2.0
    h_lon = (hit[0] + hit[2]) / 2.0
    return _haversine_m(q_lon, q_lat, h_lon, h_lat) <= distance_m


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in meters between two lon/lat points."""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2.0) ** 2
    return 6371000.0 * 2.0 * math.asin(math.sqrt(a))


def _expanded_bbox(bbox: tuple[float, float, float, float], distance_m: float) -> tuple[float, float, float, float]:
    """Expand a bbox by an approximate distance (meters) in each direction."""
    lat = (bbox[1] + bbox[3]) / 2.0
    d_lat = distance_m / _METERS_PER_DEGREE
    d_lon = distance_m / (_METERS_PER_DEGREE * max(0.01, math.cos(math.radians(lat))))
    return (bbox[0] - d_lon, bbox[1] - d_lat, bbox[2] + d_lon, bbox[3] + d_lat)
