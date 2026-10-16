"""Router exposing charge-sheet human review, field corrections, and finalization endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ..dependencies import get_review_service
from ..schemas.review import (
    AddNoteRequest,
    CorrectionRequest,
    DecisionRequest,
    HistoryResponse,
    RetrievalQueryResponse,
    ReviewDataResponse,
)
from ..services.case_review_service import CaseReviewService

router = APIRouter(prefix="/api/v1/cases/{case_id}/review", tags=["Review"])


@router.get(
    "",
    response_model=ReviewDataResponse,
    summary="Get charge-sheet review data and completeness",
)
def get_review_data(
    case_id: str,
    service: Annotated[CaseReviewService, Depends(get_review_service)],
) -> ReviewDataResponse:
    """Retrieve all charge-sheet fields with provenance, completeness breakdown, and review state."""
    return service.get_review_data(case_id)


@router.post(
    "/corrections",
    response_model=ReviewDataResponse,
    summary="Apply reviewer corrections to charge-sheet fields",
)
def apply_corrections(
    case_id: str,
    request: CorrectionRequest,
    service: Annotated[CaseReviewService, Depends(get_review_service)],
) -> ReviewDataResponse:
    """Submit reviewer corrections, creating a traceable new version and invalidating prior approval."""
    return service.apply_corrections(case_id, request)


@router.post(
    "/notes",
    response_model=ReviewDataResponse,
    summary="Add an officer review note or observation",
)
def add_note(
    case_id: str,
    request: AddNoteRequest,
    service: Annotated[CaseReviewService, Depends(get_review_service)],
) -> ReviewDataResponse:
    """Attach an audit-logged reviewer note to the charge sheet."""
    return service.add_note(case_id, request)


@router.post(
    "/decision",
    response_model=ReviewDataResponse,
    summary="Record review decision (approve, reject, request revision, or finalize)",
)
def record_decision(
    case_id: str,
    request: DecisionRequest,
    service: Annotated[CaseReviewService, Depends(get_review_service)],
) -> ReviewDataResponse:
    """Record an official review decision with state guards against critical blockers."""
    return service.record_decision(case_id, request)


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Retrieve revision and decision event history",
)
def get_history(
    case_id: str,
    service: Annotated[CaseReviewService, Depends(get_review_service)],
) -> HistoryResponse:
    """Retrieve chronological audit trail of versions, corrections, and review decisions."""
    return service.get_history(case_id)


@router.get(
    "/retrieval",
    response_model=RetrievalQueryResponse,
    summary="Search case-isolated document passages with exact provenance",
)
def search_evidence(
    case_id: str,
    query: str,
    service: Annotated[CaseReviewService, Depends(get_review_service)],
    top_k: int = 5,
) -> RetrievalQueryResponse:
    """Retrieve case-isolated document passages matching a query with exact provenance."""
    data = service.search_evidence(case_id, query, top_k=top_k)
    return RetrievalQueryResponse.model_validate(data)

