"""Artifact inspection and draft charge-sheet PDF download router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ..dependencies import get_artifact_service
from ..schemas.artifact import ArtifactListResponse
from ..services.artifact_service import ArtifactService

router = APIRouter(prefix="/api/v1/cases/{case_id}/artifacts", tags=["Artifacts"])


@router.get(
    "",
    response_model=ArtifactListResponse,
    summary="List generated case artifacts",
)
def list_artifacts(
    case_id: str,
    service: Annotated[ArtifactService, Depends(get_artifact_service)],
) -> ArtifactListResponse:
    """Retrieve relative references and availability flags for all case artifacts."""
    return service.get_artifacts(case_id)


@router.get(
    "/chargesheet.pdf",
    response_class=FileResponse,
    summary="Download draft charge-sheet PDF",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "The generated draft charge-sheet PDF file.",
        },
    },
)
def download_draft_chargesheet_pdf(
    case_id: str,
    service: Annotated[ArtifactService, Depends(get_artifact_service)],
) -> FileResponse:
    """Download the generated draft charge-sheet PDF with strict directory sandboxing."""
    pdf_path, download_filename = service.get_draft_pdf_path(case_id)
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=download_filename,
        headers={"Content-Disposition": f'inline; filename="{download_filename}"'},
    )


@router.get(
    "/chargesheet_final.pdf",
    response_class=FileResponse,
    summary="Download finalized charge-sheet PDF",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "The officially approved and finalized charge-sheet PDF file.",
        },
    },
)
def download_final_chargesheet_pdf(
    case_id: str,
    service: Annotated[ArtifactService, Depends(get_artifact_service)],
) -> FileResponse:
    """Download the officially approved and finalized charge-sheet PDF."""
    pdf_path, download_filename = service.get_final_pdf_path(case_id)
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=download_filename,
        headers={"Content-Disposition": f'inline; filename="{download_filename}"'},
    )


@router.get(
    "/content/{artifact_name}",
    summary="Retrieve parsed JSON content of a case artifact",
)
def get_artifact_content(
    case_id: str,
    artifact_name: str,
    service: Annotated[ArtifactService, Depends(get_artifact_service)],
):
    """Retrieve the parsed JSON content of an accessible case artifact."""
    return service.get_artifact_content(case_id, artifact_name)

