"""Pydantic schemas for case management and document intake."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CaseCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str | None = Field(
        default=None,
        description="Optional client-supplied case identifier (valid UUID or alphanumeric slug).",
        min_length=1,
        max_length=64,
    )
    title: str | None = Field(default=None, max_length=256)
    description: str | None = Field(default=None, max_length=2048)


class CaseCreateResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    status: str
    created_at: str
    storage_key: str


class CaseDocumentItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: str
    original_filename: str
    stored_filename: str
    size_bytes: int
    media_type: str
    uploaded_at: str


class CaseSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    created_at: str
    document_count: int
    status: str
    validation_disposition: str | None = None
    review_status: str | None = None


class CaseDetailResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    created_at: str
    title: str | None = None
    description: str | None = None
    status: str
    document_count: int
    documents: list[CaseDocumentItem] = Field(default_factory=list)
    validation_disposition: str | None = None
    review_status: str | None = None
    artifacts_available: list[str] = Field(default_factory=list)
    active_job_id: str | None = None


class CaseListResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cases: list[CaseSummary]
    total: int


class DocumentUploadItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: str
    original_filename: str
    size_bytes: int
    media_type: str
    status: str = "uploaded"
    errors: list[str] = Field(default_factory=list)


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    uploaded_count: int
    failed_count: int
    documents: list[DocumentUploadItem]


class CaseDeleteResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    status: str = "deleted"
    message: str
