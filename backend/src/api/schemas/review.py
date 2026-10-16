"""Schemas for charge-sheet human review, corrections, and decision workflows."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class CorrectionRequest(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=128)
    reviewer_name: str | None = Field(default=None, max_length=256)
    comments: str | None = Field(default=None, max_length=2000)
    corrections: dict[str, str] = Field(min_length=1)


class AddNoteRequest(BaseModel):
    author_id: str = Field(min_length=1, max_length=128)
    author_name: str | None = Field(default=None, max_length=256)
    note_text: str = Field(min_length=1, max_length=4000)


class DecisionRequest(BaseModel):
    decision: str = Field(pattern=r"^(approve|reject|request_revision|finalize)$")
    reviewer_id: str = Field(min_length=1, max_length=128)
    reviewer_name: str | None = Field(default=None, max_length=256)
    comments: str | None = Field(default=None, max_length=2000)
    rejection_reason: str | None = Field(default=None, max_length=2000)


class ReviewDataResponse(BaseModel):
    case_id: str
    status: str
    data_version: int
    charge_sheet_data: dict[str, Any]
    completeness_report: dict[str, Any]
    events: list[dict[str, Any]]
    notes: list[dict[str, Any]]
    available_versions: list[int]
    can_approve: bool
    can_finalize: bool
    is_finalized: bool
    draft_pdf_available: bool
    final_pdf_available: bool


class HistoryResponse(BaseModel):
    case_id: str
    current_version: int
    status: str
    available_versions: list[int]
    events: list[dict[str, Any]]
    notes: list[dict[str, Any]]


class RetrievalQueryResponse(BaseModel):
    case_id: str
    query: str
    total_chunks_indexed: int
    passages: list[dict[str, Any]]

