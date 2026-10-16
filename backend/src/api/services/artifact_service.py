"""Service resolving artifact metadata and draft PDF downloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...intake.storage_layout import CaseStorageLayout
from ..config import api_config
from ..exceptions import (
    ArtifactNotFoundError,
    ArtifactSecurityError,
    CaseNotFoundError,
)
from ..schemas.artifact import ArtifactItem, ArtifactListResponse
from .case_service import parse_safe_case_id


KNOWN_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("upload_manifest", "upload_manifest.json"),
    ("investigation_graph", "graph/investigation_graph.json"),
    ("canonical_investigation", "canonical/canonical_investigation.json"),
    ("validation_report", "validation/validation_report.json"),
    ("case_context", "context/case_context.json"),
    ("legal_findings", "legal/legal_findings.json"),
    ("chargesheet_data", "chargesheet/draft/ChargeSheet_v1_data.json"),
    ("chargesheet_draft", "chargesheet/draft/ChargeSheet_v1_review.pdf"),
    ("review_state", "chargesheet/review_state.json"),
)


class ArtifactService:
    def __init__(self, storage_root: Path | None = None) -> None:
        self.storage_root = (storage_root or api_config.storage_root).resolve()

    def get_artifacts(self, case_id: str) -> ArtifactListResponse:
        case_uuid, client_id = parse_safe_case_id(case_id)
        layout = CaseStorageLayout(self.storage_root, case_uuid)
        if not layout.case_directory.is_dir():
            raise CaseNotFoundError(case_id)

        artifacts: list[ArtifactItem] = []
        draft_pdf_available = False

        for name, rel_path in KNOWN_ARTIFACTS:
            artifact_file = layout.processed_directory / rel_path
            exists = artifact_file.is_file()
            size_bytes = artifact_file.stat().st_size if exists else None

            if name == "chargesheet_draft" and exists:
                draft_pdf_available = True

            safe_rel = f"processed/{rel_path}"
            artifacts.append(
                ArtifactItem(
                    name=name,
                    relative_path=safe_rel,
                    size_bytes=size_bytes,
                    exists=exists,
                )
            )

        return ArtifactListResponse(
            case_id=client_id,
            artifacts=artifacts,
            draft_pdf_available=draft_pdf_available,
        )

    def get_draft_pdf_path(self, case_id: str) -> tuple[Path, str]:
        case_uuid, client_id = parse_safe_case_id(case_id)
        layout = CaseStorageLayout(self.storage_root, case_uuid)
        if not layout.case_directory.is_dir():
            raise CaseNotFoundError(case_id)

        draft_dir = layout.processed_directory / "chargesheet" / "draft"
        all_drafts = sorted(draft_dir.glob("ChargeSheet_v*_review.pdf"))
        if all_drafts:
            pdf_path = all_drafts[-1]
        else:
            pdf_path = draft_dir / "ChargeSheet_v1_review.pdf"

        resolved_pdf = pdf_path.resolve()

        # Strict sandbox checks: must be inside both storage_root and case_directory
        try:
            if not resolved_pdf.is_relative_to(self.storage_root) or not resolved_pdf.is_relative_to(layout.case_directory.resolve()):
                raise ArtifactSecurityError("Artifact path escapes permitted case directory boundaries.")
        except AttributeError:
            # Fallback for Python < 3.9 (should not trigger on 3.12, but safe guard)
            if not str(resolved_pdf).startswith(str(self.storage_root)):
                raise ArtifactSecurityError("Artifact path escapes storage root.")

        if not pdf_path.is_file():
            raise ArtifactNotFoundError(
                f"Draft charge-sheet PDF for case '{case_id}' has not been generated yet. "
                "Please trigger case processing and await job completion."
            )

        download_filename = f"draft_chargesheet_{client_id}.pdf"
        return pdf_path, download_filename

    def get_final_pdf_path(self, case_id: str) -> tuple[Path, str]:
        case_uuid, client_id = parse_safe_case_id(case_id)
        layout = CaseStorageLayout(self.storage_root, case_uuid)
        if not layout.case_directory.is_dir():
            raise CaseNotFoundError(case_id)

        review_state_file = layout.processed_directory / "chargesheet" / "review_state.json"
        if not review_state_file.is_file():
            raise ArtifactNotFoundError(
                f"Finalized charge-sheet PDF for case '{case_id}' has not been generated yet. "
                "The charge sheet must be officially approved and finalized by an officer first."
            )
        try:
            review_state = json.loads(review_state_file.read_text(encoding="utf-8"))
            if review_state.get("status") != "finalized":
                raise ArtifactNotFoundError(
                    f"Finalized charge-sheet PDF for case '{case_id}' has not been generated yet. "
                    "The charge sheet must be officially approved and finalized by an officer first."
                )
        except (json.JSONDecodeError, OSError):
            raise ArtifactNotFoundError("Charge sheet review state is invalid.")

        final_dir = layout.processed_directory / "chargesheet" / "final"
        all_finals = sorted(final_dir.glob("ChargeSheet_v*_final.pdf"))
        if not all_finals:
            raise ArtifactNotFoundError(
                f"Finalized charge-sheet PDF for case '{case_id}' has not been generated yet. "
                "The charge sheet must be officially approved and finalized by an officer first."
            )

        pdf_path = all_finals[-1]
        resolved_pdf = pdf_path.resolve()

        try:
            if not resolved_pdf.is_relative_to(self.storage_root) or not resolved_pdf.is_relative_to(layout.case_directory.resolve()):
                raise ArtifactSecurityError("Artifact path escapes permitted case directory boundaries.")
        except AttributeError:
            if not str(resolved_pdf).startswith(str(self.storage_root)):
                raise ArtifactSecurityError("Artifact path escapes storage root.")

        download_filename = f"final_chargesheet_{client_id}.pdf"
        return pdf_path, download_filename

    def get_artifact_content(self, case_id: str, artifact_name: str) -> dict[str, Any] | list[Any]:
        """Safely retrieve the parsed JSON content of an accessible case artifact."""
        case_uuid, client_id = parse_safe_case_id(case_id)
        layout = CaseStorageLayout(self.storage_root, case_uuid)
        if not layout.case_directory.is_dir():
            raise CaseNotFoundError(case_id)

        artifacts_map = dict(KNOWN_ARTIFACTS)
        rel_path = artifacts_map.get(artifact_name)
        if not rel_path or not rel_path.endswith(".json"):
            raise ArtifactNotFoundError(f"Artifact '{artifact_name}' is not an accessible JSON artifact.")

        target_file = (layout.processed_directory / rel_path).resolve()
        try:
            if not target_file.is_relative_to(self.storage_root) or not target_file.is_relative_to(layout.case_directory.resolve()):
                raise ArtifactSecurityError("Artifact path escapes permitted case directory boundaries.")
        except AttributeError:
            if not str(target_file).startswith(str(self.storage_root)):
                raise ArtifactSecurityError("Artifact path escapes storage root.")

        if not target_file.is_file():
            raise ArtifactNotFoundError(f"Artifact '{artifact_name}' has not been generated for case '{case_id}'.")

        try:
            return json.loads(target_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ArtifactNotFoundError(f"Failed to read artifact '{artifact_name}': {exc}")

