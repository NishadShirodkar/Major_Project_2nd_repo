"""Pydantic schemas for Byomkesh AI authentication and investigator authorization."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    username: str | None = Field(default=None, max_length=128, description="Investigator username or badge number")
    badge_number: str | None = Field(default=None, max_length=128, description="Investigator badge number")
    password: str = Field(min_length=1, max_length=128, description="Authentication password")

    @property
    def identifier(self) -> str:
        return self.username or self.badge_number or ""


class OfficerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    officer_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    rank: str = Field(min_length=1, max_length=64)
    police_station: str = Field(min_length=1, max_length=128)
    badge_number: str = Field(min_length=1, max_length=64)
    role: str = Field(default="investigator")


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    token_type: str = "Bearer"
    expires_in_seconds: int = 86400  # 24 hours
    officer: OfficerProfile


class TokenValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    officer: OfficerProfile
