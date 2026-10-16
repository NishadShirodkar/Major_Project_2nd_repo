"""Pydantic schemas for case artifacts and draft PDF downloads."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ArtifactItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    relative_path: str
    size_bytes: int | None = None
    exists: bool


class ArtifactListResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    artifacts: list[ArtifactItem] = Field(default_factory=list)
    draft_pdf_available: bool = False
