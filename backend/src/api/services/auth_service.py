"""Authentication and session management service for Byomkesh AI."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone
from typing import NamedTuple

from ..exceptions import APIError
from ..schemas.auth import LoginResponse, OfficerProfile


class AuthenticationFailedError(APIError):
    def __init__(self, message: str = "Invalid officer username or password.") -> None:
        super().__init__(message=message, status_code=401, error_code="AUTHENTICATION_FAILED")


class InvalidTokenError(APIError):
    def __init__(self, message: str = "Authentication session is invalid or has expired.") -> None:
        super().__init__(message=message, status_code=401, error_code="INVALID_TOKEN")


class ActiveSession(NamedTuple):
    token: str
    officer: OfficerProfile
    created_at: float
    expires_at: float


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()


# Configured authorized officer directory with PBKDF2-hashed credentials
_SALT = "byomkesh_forensic_auth_salt_2024"

_OFFICER_RECORDS = {
    "inspector_sharma": {
        "password_hash": _hash_password("investigator123", _SALT),
        "officer": OfficerProfile(
            officer_id="dl_rn_4501",
            name="Inspector Ramesh Sharma",
            rank="Station House Officer (SHO)",
            police_station="Rajinder Nagar Police Station, Delhi",
            badge_number="DL-RN-4501",
            role="sho",
        ),
    },
    "officer_rao": {
        "password_hash": _hash_password("delhipolice2026", _SALT),
        "officer": OfficerProfile(
            officer_id="dl_ci_1082",
            name="Sub-Inspector K. V. Rao",
            rank="Investigating Officer",
            police_station="Central Division Police Station",
            badge_number="DL-CI-1082",
            role="investigator",
        ),
    },
    "dsp_byomkesh": {
        "password_hash": _hash_password("byomkeshai2026", _SALT),
        "officer": OfficerProfile(
            officer_id="dl_cid_001",
            name="DSP Byomkesh Bakshi",
            rank="Forensic Investigation Director",
            police_station="Crime Investigation Department (CID)",
            badge_number="DL-CID-001",
            role="director",
        ),
    },
    "investigator": {
        "password_hash": _hash_password("byomkesh123", _SALT),
        "officer": OfficerProfile(
            officer_id="dl_inv_992",
            name="Investigating Officer",
            rank="Sub-Inspector",
            police_station="Delhi Police District Headquarters",
            badge_number="DL-INV-992",
            role="investigator",
        ),
    },
}


class AuthService:
    """Thread-safe authentication service managing active investigator sessions."""

    _sessions: dict[str, ActiveSession] = {}

    @classmethod
    def authenticate(cls, username: str, password: str) -> LoginResponse:
        key = username.strip().lower()
        record = _OFFICER_RECORDS.get(key)
        if not record:
            # Also search by badge number
            for rec in _OFFICER_RECORDS.values():
                if rec["officer"].badge_number.lower() == key:
                    record = rec
                    break

        if not record:
            raise AuthenticationFailedError("Invalid officer username or badge number.")

        expected_hash = record["password_hash"]
        provided_hash = _hash_password(password, _SALT)

        if not hmac.compare_digest(expected_hash, provided_hash):
            raise AuthenticationFailedError("Invalid password for officer credentials.")

        now = time.time()
        ttl = 86400.0  # 24 hours
        token = secrets.token_hex(32)
        session = ActiveSession(
            token=token,
            officer=record["officer"],
            created_at=now,
            expires_at=now + ttl,
        )
        cls._sessions[token] = session

        return LoginResponse(
            token=token,
            token_type="Bearer",
            expires_in_seconds=int(ttl),
            officer=record["officer"],
        )

    @classmethod
    def validate_token(cls, token: str) -> OfficerProfile:
        if not token:
            raise InvalidTokenError("Missing authorization token.")

        # Strip Bearer if present
        if token.startswith("Bearer "):
            token = token[7:].strip()

        session = cls._sessions.get(token)
        if not session:
            raise InvalidTokenError("Session not found or already terminated.")

        if time.time() > session.expires_at:
            cls._sessions.pop(token, None)
            raise InvalidTokenError("Session has expired. Please log in again.")

        return session.officer

    @classmethod
    def revoke_token(cls, token: str) -> bool:
        if token.startswith("Bearer "):
            token = token[7:].strip()
        return cls._sessions.pop(token, None) is not None
