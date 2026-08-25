from __future__ import annotations

from fastapi import APIRouter

from ..errors import GeoFrontError
from ..jobs import get_job_manager

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    record = get_job_manager().get(job_id)
    if record is None:
        raise GeoFrontError(
            code="job_not_found",
            message=f"Job not found: {job_id}",
            status_code=404,
        )
    return record.public()
