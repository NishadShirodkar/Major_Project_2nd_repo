"""Evidence-backed data contract for the supplied charge-sheet sample."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from ..domain.common import DomainModel, SourceReference


class FieldStatus(StrEnum):
    POPULATED = "populated"
    UNAVAILABLE = "unavailable"
    CONFLICT = "conflict"
    REVIEW_REQUIRED = "review_required"
    NOT_APPLICABLE = "not_applicable"
    REVIEWER_CORRECTED = "reviewer_corrected"
    NOT_FOUND = "not_found"
    EXTRACTION_FAILED = "extraction_failed"


class ChargeSheetField(DomainModel):
    value: str | None = None
    status: FieldStatus
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_references: tuple[SourceReference, ...] = ()
    review_required: bool = False
    origin: str = "extracted"  # "extracted" | "derived" | "reviewer_corrected" | "default_unavailable"
    original_value: str | None = None
    corrected_by: str | None = None
    corrected_at: str | None = None
    correction_notes: str | None = None

    @model_validator(mode="after")
    def populated_values_require_provenance(self) -> "ChargeSheetField":
        if self.status in {FieldStatus.POPULATED, FieldStatus.REVIEW_REQUIRED}:
            if not self.value or not self.source_references:
                raise ValueError("Rendered charge-sheet values require source references")
        elif self.status == FieldStatus.REVIEWER_CORRECTED:
            if not self.value:
                raise ValueError("Reviewer corrected fields require a value")
            if not self.source_references and not self.corrected_by:
                raise ValueError("Reviewer corrected fields require either source references or reviewer identity")
        if self.status in {FieldStatus.UNAVAILABLE, FieldStatus.NOT_APPLICABLE, FieldStatus.NOT_FOUND, FieldStatus.EXTRACTION_FAILED} and self.value:
            raise ValueError("Unavailable/unpopulated fields cannot contain an unsupported value")
        return self

    @property
    def rendered(self) -> str:
        if self.value:
            return self.value
        if self.status == FieldStatus.NOT_FOUND:
            return "Not found in uploaded evidence"
        if self.status == FieldStatus.EXTRACTION_FAILED:
            return "Extraction failed (Requires manual verification)"
        if self.status == FieldStatus.CONFLICT:
            return "Conflicting source information (Review Required)"
        if self.status == FieldStatus.NOT_APPLICABLE:
            return "Not Applicable"
        if self.status == FieldStatus.REVIEW_REQUIRED:
            return "Requires manual verification"
        return "Not Available in Investigation Records"


class IF5Row(DomainModel):
    serial: int = Field(ge=1)
    description: ChargeSheetField
    exhibit: ChargeSheetField


class ChargeSheetLegalFinding(DomainModel):
    """A reviewable legal conclusion without upgrading its evidentiary status."""

    offence: ChargeSheetField
    proposed_section: ChargeSheetField
    description: ChargeSheetField
    status: str
    evidence_strength: str
    review_required: bool
    supporting_evidence: tuple[ChargeSheetField, ...] = ()
    contradicting_evidence: tuple[ChargeSheetField, ...] = ()
    ingredient_assessments: tuple[dict, ...] = ()
    retrieved_passages: tuple[dict, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    reasoning_summary: str | None = None
    review_warnings: tuple[str, ...] = ()


class ChargeSheetReviewItem(DomainModel):
    category: str
    description: str
    source_references: tuple[SourceReference, ...] = ()
    review_required: bool = True


class ChargeSheetData(DomainModel):
    case_id: UUID
    disposition: str
    version: int = Field(default=1, ge=1)
    case_number: ChargeSheetField
    police_station: ChargeSheetField
    court: ChargeSheetField
    case_summary: ChargeSheetField
    detailed_facts: ChargeSheetField
    investigation_conducted: ChargeSheetField
    evidence_analysis: ChargeSheetField
    complainants: tuple[IF5Row, ...] = ()
    victims: tuple[IF5Row, ...] = ()
    accused: tuple[IF5Row, ...] = ()
    witnesses: tuple[IF5Row, ...] = ()
    timeline: tuple[IF5Row, ...] = ()
    documentary_evidence: tuple[IF5Row, ...] = ()
    material_evidence: tuple[IF5Row, ...] = ()
    medical_findings: tuple[ChargeSheetField, ...] = ()
    forensic_findings: tuple[ChargeSheetField, ...] = ()
    vehicle_findings: tuple[ChargeSheetField, ...] = ()
    legal_sections: tuple[ChargeSheetField, ...] = ()
    legal_findings: tuple[ChargeSheetLegalFinding, ...] = ()
    conflicts: tuple[ChargeSheetReviewItem, ...] = ()
    missing_information: tuple[ChargeSheetReviewItem, ...] = ()
    annexures: tuple[IF5Row, ...] = ()
    final_opinion: ChargeSheetField
    signature: ChargeSheetField

    @property
    def content_hash(self) -> str:
        """Stable identity for the exact charge-sheet content and version."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
