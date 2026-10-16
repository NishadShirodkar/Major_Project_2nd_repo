"""API configuration and environment variable loading for Byomkesh AI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, Field

from ..config import Config


class APIConfig(BaseModel):
    """Runtime configuration for the FastAPI service layer."""

    service_name: str = "byomkesh-ai"
    version: str = "1.0.0"
    host: str = Field(default_factory=lambda: os.getenv("API_HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))

    # Storage roots
    storage_root: Path = Field(
        default_factory=lambda: Path(os.getenv("OUTPUT_DIR", Config.OUTPUT_DIR)).resolve()
    )

    # Upload limits
    max_upload_file_size_bytes: int = Field(
        default_factory=lambda: int(
            os.getenv("MAX_UPLOAD_FILE_SIZE_BYTES", str(Config.MAX_UPLOAD_FILE_SIZE_BYTES))
        )
    )
    max_case_upload_size_bytes: int = Field(
        default_factory=lambda: int(
            os.getenv("MAX_CASE_UPLOAD_SIZE_BYTES", str(Config.MAX_CASE_UPLOAD_SIZE_BYTES))
        )
    )

    # Legal reference defaults
    legal_reference_path: Path = Field(
        default_factory=lambda: (
            Path(Config.LEGAL_REFERENCE_PATH).resolve()
            if Config.LEGAL_REFERENCE_PATH
            else (Path(__file__).resolve().parents[2] / "references" / "legal" / "bns_sections.json")
        )
    )
    legal_reference_version: str = Field(
        default_factory=lambda: os.getenv(
            "LEGAL_REFERENCE_VERSION", Config.LEGAL_REFERENCE_VERSION or "bns-2023-2024-07-01"
        )
    )

    # CORS configuration
    cors_allowed_origins: Sequence[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "CORS_ALLOWED_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if origin.strip()
        ]
    )


api_config = APIConfig()
