"""Authentication router for Byomkesh AI."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, status

from ..schemas.auth import LoginRequest, LoginResponse, OfficerProfile, TokenValidationResponse
from ..services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate officer credentials and issue session token",
)
def login(request: LoginRequest) -> LoginResponse:
    """Validate officer username/badge and password, issuing a 24-hour Bearer token."""
    return AuthService.authenticate(request.identifier, request.password)


@router.get(
    "/me",
    response_model=TokenValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate active session token and retrieve current officer profile",
)
def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> TokenValidationResponse:
    """Verify session token from Authorization header and return officer profile."""
    officer = AuthService.validate_token(authorization or "")
    return TokenValidationResponse(valid=True, officer=officer)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Terminate active session token",
)
def logout(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    """Revoke session token."""
    if authorization:
        AuthService.revoke_token(authorization)
    return {"status": "logged_out", "message": "Officer session successfully terminated."}
