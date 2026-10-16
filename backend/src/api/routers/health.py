"""Health and readiness check endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from ...config import Config
from ..config import api_config
from ..dependencies import get_storage_root
from ..schemas.common import HealthResponse, ReadyResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """Return process health status."""
    return HealthResponse(status="ok", service=api_config.service_name, version=api_config.version)


@router.get("/ready", response_model=ReadyResponse, summary="Readiness probe")
def ready(
    response: Response,
    storage_root: Annotated[Path, Depends(get_storage_root)],
) -> ReadyResponse:
    """Assess whether the service is ready to process cases without invoking external LLMs."""
    checks: dict[str, bool] = {}
    details: dict[str, str] = {}

    # Check 1: Storage directory accessibility
    try:
        storage_root.mkdir(parents=True, exist_ok=True)
        probe_file = storage_root / ".write_probe"
        probe_file.write_text("probe", encoding="utf-8")
        probe_file.unlink()
        checks["storage_root"] = True
        details["storage_root"] = f"Accessible at {storage_root}"
    except Exception as exc:
        checks["storage_root"] = False
        details["storage_root"] = f"Inaccessible: {exc}"

    # Check 2: Legal reference dataset
    legal_path = api_config.legal_reference_path
    if legal_path.is_file():
        try:
            data = json.loads(legal_path.read_text(encoding="utf-8"))
            if "references" in data and "version" in data:
                checks["legal_reference"] = True
                details["legal_reference"] = f"Valid version '{data['version']}' at {legal_path.name}"
            else:
                checks["legal_reference"] = False
                details["legal_reference"] = "Malformed legal reference dataset structure."
        except Exception as exc:
            checks["legal_reference"] = False
            details["legal_reference"] = f"Cannot read dataset: {exc}"
    else:
        checks["legal_reference"] = False
        details["legal_reference"] = f"File not found: {legal_path}"

    # Check 3: Gemini configuration (readiness reports whether key is present, but never calls the API)
    gemini_key_present = bool(Config.GEMINI_API_KEY and Config.GEMINI_API_KEY.strip())
    checks["gemini_configured"] = gemini_key_present
    details["gemini_configured"] = "API key configured" if gemini_key_present else "API key not set (mock mode required for processing)"

    # Service is considered ready if storage and legal references are valid
    is_ready = checks.get("storage_root", False) and checks.get("legal_reference", False)

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyResponse(
        status="ready" if is_ready else "not_ready",
        ready=is_ready,
        checks=checks,
        details=details,
    )
