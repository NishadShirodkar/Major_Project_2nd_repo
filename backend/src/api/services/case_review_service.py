"""Case-isolated review service managing charge-sheet corrections, reviews, and finalization."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from ...chargesheet.completeness_reporter import CompletenessReporter
from ...chargesheet.form_if5_schema import ChargeSheetData, ChargeSheetField, FieldStatus
from ...intake.storage_layout import CaseStorageLayout
from ...rendering.if5_renderer import IF5Renderer
from ...review.review_models import ChargeSheetReview, ReviewEventType, ReviewStatus
from ...review.review_service import ReviewLifecycleError, ReviewService
from ..config import api_config
from ..exceptions import ArtifactNotFoundError, CaseNotFoundError
from ..schemas.review import (
    AddNoteRequest,
    CorrectionRequest,
    DecisionRequest,
    HistoryResponse,
    ReviewDataResponse,
)
from .case_service import parse_safe_case_id

_VERSION_RE = re.compile(r"^ChargeSheet_v(\d+)_data\.json$")


class CaseReviewService:
    def __init__(self, storage_root: Path | None = None) -> None:
        self.storage_root = (storage_root or api_config.storage_root).resolve()
        self.review_service = ReviewService()
        self.completeness_reporter = CompletenessReporter()
        self.renderer = IF5Renderer()

    def _get_layout(self, case_id: str) -> tuple[CaseStorageLayout, UUID, str]:
        case_uuid, client_id = parse_safe_case_id(case_id)
        layout = CaseStorageLayout(self.storage_root, case_uuid)
        if not layout.case_directory.is_dir():
            raise CaseNotFoundError(case_id)
        return layout, case_uuid, client_id

    def _find_available_versions(self, layout: CaseStorageLayout) -> list[int]:
        draft_dir = layout.processed_directory / "chargesheet" / "draft"
        if not draft_dir.is_dir():
            return []
        versions: list[int] = []
        for file in draft_dir.glob("ChargeSheet_v*_data.json"):
            match = _VERSION_RE.match(file.name)
            if match:
                versions.append(int(match.group(1)))
        return sorted(versions)

    def _load_latest_data(self, layout: CaseStorageLayout) -> ChargeSheetData:
        versions = self._find_available_versions(layout)
        if not versions:
            raise ArtifactNotFoundError("No charge-sheet data found for this case. Process the case first.")
        latest_version = versions[-1]
        data_file = layout.processed_directory / "chargesheet" / "draft" / f"ChargeSheet_v{latest_version}_data.json"
        if not data_file.is_file():
            raise ArtifactNotFoundError(f"Charge-sheet data file missing for version {latest_version}.")
        raw_json = data_file.read_text(encoding="utf-8")
        return ChargeSheetData.model_validate_json(raw_json)

    def _load_or_create_review(self, layout: CaseStorageLayout, data: ChargeSheetData) -> ChargeSheetReview:
        state_file = layout.processed_directory / "chargesheet" / "review_state.json"
        if state_file.is_file():
            try:
                raw_json = state_file.read_text(encoding="utf-8")
                review = ChargeSheetReview.model_validate_json(raw_json)
                if review.data_version == data.version and review.data_content_hash == data.content_hash:
                    return review
                # If data was updated but review wasn't updated yet, replace data
                if review.status != ReviewStatus.FINALIZED and data.version > review.data_version:
                    updated_review = self.review_service.replace_data(review, data)
                    state_file.write_text(json.dumps(updated_review.model_dump(mode="json"), indent=2), encoding="utf-8")
                    return updated_review
                return review
            except Exception:
                pass

        # Create new review draft
        created = self.review_service.create_draft(data)
        review = self.review_service.submit_for_review(created, data)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(review.model_dump(mode="json"), indent=2), encoding="utf-8")
        return review

    def get_review_data(self, case_id: str) -> ReviewDataResponse:
        layout, _, client_id = self._get_layout(case_id)
        data = self._load_latest_data(layout)
        review = self._load_or_create_review(layout, data)
        completeness = self.completeness_reporter.report(data)
        versions = self._find_available_versions(layout)

        draft_pdf = layout.processed_directory / "chargesheet" / "draft" / f"ChargeSheet_v{data.version}_review.pdf"
        draft_available = draft_pdf.is_file() or (layout.processed_directory / "chargesheet" / "draft" / "ChargeSheet_v1_review.pdf").is_file()

        final_pdf = layout.processed_directory / "chargesheet" / "final" / f"ChargeSheet_v{data.version}_final.pdf"
        final_available = final_pdf.is_file()

        is_finalized = review.status == ReviewStatus.FINALIZED
        final_completeness = self.completeness_reporter.report(data, is_finalization_target=True)
        can_approve = (
            review.status == ReviewStatus.REVIEW_REQUIRED
            and len(completeness.critical_blockers) == 0
            and data.disposition != "final_blocked"
        )
        can_finalize = (
            review.status == ReviewStatus.APPROVED
            and len(final_completeness.critical_blockers) == 0
            and data.disposition != "final_blocked"
        )

        return ReviewDataResponse(
            case_id=client_id,
            status=review.status.value,
            data_version=data.version,
            charge_sheet_data=data.model_dump(mode="json"),
            completeness_report=completeness.model_dump(mode="json"),
            events=[e.model_dump(mode="json") for e in review.events],
            notes=[n.model_dump(mode="json") for n in review.notes],
            available_versions=versions,
            can_approve=can_approve,
            can_finalize=can_finalize,
            is_finalized=is_finalized,
            draft_pdf_available=draft_available,
            final_pdf_available=final_available,
        )

    def apply_corrections(self, case_id: str, request: CorrectionRequest) -> ReviewDataResponse:
        layout, _, _ = self._get_layout(case_id)
        current_data = self._load_latest_data(layout)
        current_review = self._load_or_create_review(layout, current_data)

        if current_review.status == ReviewStatus.FINALIZED:
            raise ReviewLifecycleError("FINALIZED charge sheets are immutable and cannot be corrected.")

        new_version = current_data.version + 1
        updated_fields: dict[str, Any] = {}
        now = datetime.now(timezone.utc)

        allowed_text_fields = {
            "case_summary",
            "detailed_facts",
            "investigation_conducted",
            "evidence_analysis",
            "final_opinion",
            "signature",
            "court",
            "police_station",
            "case_number",
        }

        for field_name, new_val in request.corrections.items():
            if field_name not in allowed_text_fields:
                raise ReviewLifecycleError(f"Field '{field_name}' is not an eligible reviewer-correctable field.")
            current_field: ChargeSheetField = getattr(current_data, field_name)
            clean_val = new_val.strip() if new_val else ""
            updated_fields[field_name] = ChargeSheetField(
                value=clean_val if clean_val else None,
                status=FieldStatus.REVIEWER_CORRECTED if clean_val else FieldStatus.UNAVAILABLE,
                origin="reviewer_corrected",
                original_value=current_field.value,
                corrected_by=request.reviewer_id,
                corrected_at=now.isoformat(),
                correction_notes=request.comments,
                source_references=current_field.source_references,
                review_required=False,
            )

        new_data = current_data.model_copy(update={**updated_fields, "version": new_version})

        # Save revised data
        draft_dir = layout.processed_directory / "chargesheet" / "draft"
        draft_dir.mkdir(parents=True, exist_ok=True)
        new_data_path = draft_dir / f"ChargeSheet_v{new_version}_data.json"
        new_data_path.write_text(json.dumps(new_data.model_dump(mode="json"), indent=2), encoding="utf-8")

        # Render revised draft PDF
        new_pdf_path = draft_dir / f"ChargeSheet_v{new_version}_review.pdf"
        self.renderer.render(new_data, new_pdf_path)

        # Invalidate prior approval and record revision
        updated_review = self.review_service.replace_data(current_review, new_data)
        # Log correction event
        updated_review = self.review_service._event(
            updated_review,
            ReviewEventType.CORRECTION_APPLIED,
            actor_id=request.reviewer_id.strip(),
            metadata={
                "fields": ", ".join(request.corrections.keys()),
                "comments": request.comments or "",
            },
        )

        # Save review state
        state_file = layout.processed_directory / "chargesheet" / "review_state.json"
        state_file.write_text(json.dumps(updated_review.model_dump(mode="json"), indent=2), encoding="utf-8")

        return self.get_review_data(case_id)

    def add_note(self, case_id: str, request: AddNoteRequest) -> ReviewDataResponse:
        layout, _, _ = self._get_layout(case_id)
        current_data = self._load_latest_data(layout)
        current_review = self._load_or_create_review(layout, current_data)

        updated_review = self.review_service.add_note(
            current_review,
            author_id=request.author_id.strip(),
            author_name=request.author_name,
            note_text=request.note_text.strip(),
        )

        state_file = layout.processed_directory / "chargesheet" / "review_state.json"
        state_file.write_text(json.dumps(updated_review.model_dump(mode="json"), indent=2), encoding="utf-8")

        return self.get_review_data(case_id)

    def record_decision(self, case_id: str, request: DecisionRequest) -> ReviewDataResponse:
        layout, _, _ = self._get_layout(case_id)
        current_data = self._load_latest_data(layout)
        current_review = self._load_or_create_review(layout, current_data)

        if request.decision == "approve":
            if not request.reviewer_id or not request.reviewer_id.strip():
                raise ReviewLifecycleError("A reviewer identity is required")
            completeness = self.completeness_reporter.report(current_data)
            if len(completeness.critical_blockers) > 0:
                blockers_msg = "; ".join(completeness.critical_blockers)
                raise ReviewLifecycleError(
                    f"Approval blocked: {len(completeness.critical_blockers)} critical blocker(s) unresolved: {blockers_msg}"
                )
            if current_review.status == ReviewStatus.DRAFT:
                current_review = self.review_service.submit_for_review(current_review, current_data)
            updated_review = self.review_service.approve(
                current_review,
                current_data,
                reviewer_id=request.reviewer_id.strip(),
                reviewer_name=request.reviewer_name,
                comments=request.comments,
            )
        elif request.decision == "reject":
            if not request.reviewer_id or not request.reviewer_id.strip():
                raise ReviewLifecycleError("A reviewer identity is required")
            reason = (request.rejection_reason or "").strip()
            if not reason:
                raise ReviewLifecycleError("A rejection reason is required")
            updated_review = self.review_service.reject(
                current_review,
                current_data,
                reviewer_id=request.reviewer_id.strip(),
                rejection_reason=reason,
                comments=request.comments,
            )
        elif request.decision == "request_revision":
            if not request.reviewer_id or not request.reviewer_id.strip():
                raise ReviewLifecycleError("A reviewer identity is required")
            comments = (request.comments or "").strip()
            if not comments:
                raise ReviewLifecycleError("Revision comments are required")
            updated_review = self.review_service.request_revision(
                current_review,
                current_data,
                reviewer_id=request.reviewer_id.strip(),
                comments=comments,
            )
        elif request.decision == "finalize":
            if current_review.status != ReviewStatus.APPROVED:
                raise ReviewLifecycleError(
                    f"Charge sheet cannot be finalized from status '{current_review.status.value}'. Must be approved first."
                )
            completeness = self.completeness_reporter.report(current_data, is_finalization_target=True)
            if len(completeness.critical_blockers) > 0:
                blockers_msg = "; ".join(completeness.critical_blockers)
                raise ReviewLifecycleError(
                    f"Finalization blocked: {len(completeness.critical_blockers)} critical blocker(s) unresolved: {blockers_msg}"
                )
            updated_review = self.review_service.finalize(
                current_review,
                current_data,
                storage_root=self.storage_root,
            )
        else:
            raise ReviewLifecycleError(f"Unknown decision type '{request.decision}'.")

        state_file = layout.processed_directory / "chargesheet" / "review_state.json"
        state_file.write_text(json.dumps(updated_review.model_dump(mode="json"), indent=2), encoding="utf-8")

        return self.get_review_data(case_id)

    def get_history(self, case_id: str) -> HistoryResponse:
        layout, _, client_id = self._get_layout(case_id)
        current_data = self._load_latest_data(layout)
        current_review = self._load_or_create_review(layout, current_data)
        versions = self._find_available_versions(layout)

        return HistoryResponse(
            case_id=client_id,
            current_version=current_data.version,
            status=current_review.status.value,
            available_versions=versions,
            events=[e.model_dump(mode="json") for e in current_review.events],
            notes=[n.model_dump(mode="json") for n in current_review.notes],
        )

    def get_final_pdf_path(self, case_id: str) -> tuple[Path, str]:
        layout, _, client_id = self._get_layout(case_id)
        current_data = self._load_latest_data(layout)
        current_review = self._load_or_create_review(layout, current_data)
        if current_review.status != ReviewStatus.FINALIZED:
            raise ArtifactNotFoundError(
                f"Finalized charge-sheet PDF for case '{case_id}' does not exist. "
                "The charge sheet must be approved and finalized by an officer first."
            )
        final_dir = layout.processed_directory / "chargesheet" / "final"
        final_pdf = final_dir / f"ChargeSheet_v{current_data.version}_final.pdf"
        if not final_pdf.is_file():
            any_final = sorted(final_dir.glob("ChargeSheet_v*_final.pdf"))
            if any_final:
                final_pdf = any_final[-1]
            else:
                raise ArtifactNotFoundError(
                    f"Finalized charge-sheet PDF for case '{case_id}' does not exist. "
                    "The charge sheet must be approved and finalized by an officer first."
                )

        return final_pdf, f"finalized_chargesheet_{client_id}.pdf"

    def search_evidence(self, case_id: str, query: str, top_k: int = 5) -> dict[str, Any]:
        layout, case_uuid, client_id = self._get_layout(case_id)
        from ...config import Config
        from ...rag.case_retriever import CaseRetriever
        from ...rag.embedding_provider import GeminiEmbeddingProvider, NoOpEmbeddingProvider

        emb = GeminiEmbeddingProvider(Config.GEMINI_API_KEY) if Config.GEMINI_API_KEY else NoOpEmbeddingProvider()
        retriever = CaseRetriever(self.storage_root, case_uuid, embedding_provider=emb)
        passages = retriever.retrieve(query, top_k=top_k)
        return {
            "case_id": client_id,
            "query": query,
            "total_chunks_indexed": len(retriever.chunks),
            "passages": [p.model_dump(mode="json") for p in passages],
        }

