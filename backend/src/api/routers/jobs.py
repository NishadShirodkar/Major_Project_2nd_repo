"""Job status and workflow execution monitoring router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ..dependencies import get_job_service
from ..schemas.job import JobStatusResponse
from ..services.job_service import JobService

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Query background workflow job status",
)
def get_job_status(
    job_id: str,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobStatusResponse:
    """Retrieve truthful execution status, stage history, and artifact references for a job."""
    return service.get_job(job_id)
