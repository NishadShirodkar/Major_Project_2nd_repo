"""Common request and response schemas."""

from __future__ import annotations

from typing import Any, Mapping
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = "ok"
    service: str = "byomkesh-ai"
    version: str = "1.0.0"


class ReadyResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str
    ready: bool
    checks: dict[str, bool]
    details: dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    error: str
    detail: str | list[Any] | None = None
    error_code: str = "ERROR"
