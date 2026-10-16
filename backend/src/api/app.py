"""Main FastAPI application entry point for Byomkesh AI."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..review.review_service import ReviewLifecycleError
from .config import api_config
from .exceptions import APIError
from .routers import (
    artifacts_router,
    auth_router,
    cases_router,
    health_router,
    jobs_router,
    review_router,
)

logger = logging.getLogger("byomkesh.api")


def create_app() -> FastAPI:
    """Create and configure the Byomkesh AI FastAPI application."""
    application = FastAPI(
        title="Byomkesh AI — Investigation Intelligence & Charge-Sheet API",
        description=(
            "REST API exposing the typed nine-stage investigation processing pipeline, "
            "canonical knowledge graph, evidence validation, and draft charge-sheet generation."
        ),
        version=api_config.version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware allowing necessary investigation dashboard methods
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(api_config.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Exception Handlers
    @application.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        content = {
            "error": exc.error_code,
            "detail": exc.message,
            "error_code": exc.error_code,
        }
        if getattr(exc, "job_id", None):
            content["job_id"] = exc.job_id
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": err.get("loc"), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "detail": details,
                "error_code": "VALIDATION_ERROR",
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server exception processing %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "detail": "An unexpected error occurred while processing the request.",
                "error_code": "INTERNAL_ERROR",
            },
        )

    @application.exception_handler(ReviewLifecycleError)
    async def review_lifecycle_error_handler(request: Request, exc: ReviewLifecycleError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "REVIEW_LIFECYCLE_ERROR",
                "detail": str(exc),
                "error_code": "REVIEW_LIFECYCLE_ERROR",
            },
        )

    # Include Routers
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(cases_router)
    application.include_router(jobs_router)
    application.include_router(artifacts_router)
    application.include_router(review_router)

    return application


app = create_app()
