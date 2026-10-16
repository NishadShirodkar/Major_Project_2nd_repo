"""Case management, document uploads, and workflow processing endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from ..dependencies import get_case_service, get_job_service
from ..schemas.case import (
    CaseCreateRequest,
    CaseCreateResponse,
    CaseDeleteResponse,
    CaseDetailResponse,
    CaseListResponse,
    DocumentUploadResponse,
)
from ..schemas.job import JobProcessRequest, JobStartResponse
from ..services.case_service import CaseService, parse_safe_case_id
from ..services.job_service import JobService

router = APIRouter(prefix="/api/v1/cases", tags=["Cases"])


@router.post(
    "",
    response_model=CaseCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an investigation workspace",
)
def create_case(
    payload: CaseCreateRequest | None = None,
    service: Annotated[CaseService, Depends(get_case_service)] = None,
) -> CaseCreateResponse:
    """Create a new isolated case workspace. Generates a safe UUID if not client-supplied."""
    req = payload or CaseCreateRequest()
    return service.create_case(case_id=req.case_id, title=req.title, description=req.description)


@router.get(
    "",
    response_model=CaseListResponse,
    summary="List all known investigation cases",
)
def list_cases(
    service: Annotated[CaseService, Depends(get_case_service)],
) -> CaseListResponse:
    """List metadata for all active cases in the storage root."""
    return service.list_cases()


@router.get(
    "/{case_id}",
    response_model=CaseDetailResponse,
    summary="Retrieve case details, documents, and status",
)
def get_case(
    case_id: str,
    service: Annotated[CaseService, Depends(get_case_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> CaseDetailResponse:
    """Return structured metadata, document list, and processing dispositions for a single case."""
    detail = service.get_case(case_id)
    try:
        case_uuid, _ = parse_safe_case_id(case_id)
        active_job = job_service.get_active_job_for_case(case_uuid)
        if active_job:
            return detail.model_copy(update={"active_job_id": active_job})
    except Exception:
        pass
    return detail


@router.post(
    "/{case_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload investigation documents",
)
def upload_documents(
    case_id: str,
    files: Annotated[list[UploadFile], File(description="One or more investigation source documents")],
    service: Annotated[CaseService, Depends(get_case_service)],
) -> DocumentUploadResponse:
    """Upload documents via multipart/form-data with size, extension, and corruption verification."""
    return service.upload_documents(case_id, files)


@router.post(
    "/{case_id}/process",
    response_model=JobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger the 9-stage production workflow",
)
def process_case(
    case_id: str,
    payload: JobProcessRequest | None = None,
    service: Annotated[JobService, Depends(get_job_service)] = None,
) -> JobStartResponse:
    """Trigger the nine-stage pipeline asynchronously. Rejects concurrent jobs on the same case."""
    req = payload or JobProcessRequest()
    return service.start_job(case_id, resume=req.resume, mock_llm=req.mock_llm)


@router.delete(
    "/{case_id}",
    response_model=CaseDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Permanently delete an investigation case workspace",
)
def delete_case(
    case_id: str,
    service: Annotated[CaseService, Depends(get_case_service)],
) -> CaseDeleteResponse:
    """Permanently delete a case workspace, all uploaded files, and generated artifacts."""
    return service.delete_case(case_id)


@router.post(
    "/{case_id}/reset-processing",
    status_code=status.HTTP_200_OK,
    summary="Reset any hung or active background processing job for a case",
)
def reset_case_processing(
    case_id: str,
    service: Annotated[JobService, Depends(get_job_service)],
) -> dict[str, str]:
    """Force release case processing lock and mark in-flight jobs as cancelled."""
    service.reset_case_processing(case_id)
    return {"status": "reset", "case_id": case_id, "message": "Case processing lock released successfully."}
