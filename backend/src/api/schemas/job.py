"""Pydantic schemas for workflow processing jobs."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class JobProcessRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resume: bool = Field(
        default=False,
        description="Whether to reuse validated cached OCR artifacts for this case.",
    )
    mock_llm: bool = Field(
        default=False,
        description="Run in deterministic mock mode without invoking Gemini API.",
    )


class JobStartResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str
    case_id: str
    status: str
    message: str


class StageRecordItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stage_name: str
    status: str
    error_message: str | None = None


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str
    case_id: str
    status: str  # queued, running, completed, failed
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    current_stage: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    stage_records: list[StageRecordItem] = Field(default_factory=list)
    error: str | None = None
    validation_disposition: str | None = None
    artifacts_available: list[str] = Field(default_factory=list)
