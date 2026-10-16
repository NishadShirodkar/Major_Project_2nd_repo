"""Typed, review-oriented legal recommendation models."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from ..domain.common import DomainModel, SourceReference
from ..rag.rag_models import RetrievedPassage


class LegalFindingStatus(StrEnum):
    SUPPORTED = "supported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTED = "conflicted"
    REVIEW_REQUIRED = "review_required"


class EvidenceStrength(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceMapping(DomainModel):
    source_document_id: UUID
    field_path: str
    description: str
    source_references: tuple[SourceReference, ...] = Field(min_length=1)


class IngredientStatus(StrEnum):
    SUPPORTED = "supported"
    NOT_ESTABLISHED = "not_established"
    REQUIRES_REVIEW = "requires_review"


class IngredientAssessment(DomainModel):
    ingredient_name: str
    status: IngredientStatus
    supporting_evidence_ids: tuple[str, ...] = ()
    reasoning: str
    retrieved_passages: tuple[RetrievedPassage, ...] = ()


class LegalFinding(DomainModel):
    finding_id: UUID = Field(default_factory=uuid4)
    legal_reference_id: UUID
    offence: str
    proposed_section: str | None = None
    statute: str = "The Bharatiya Nyaya Sanhita, 2023"
    description: str
    supporting_evidence: tuple[EvidenceMapping, ...] = Field(min_length=1)
    contradicting_evidence: tuple[EvidenceMapping, ...] = ()
    ingredient_assessments: tuple[IngredientAssessment, ...] = ()
    retrieved_passages: tuple[RetrievedPassage, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    reasoning_summary: str | None = None
    review_warnings: tuple[str, ...] = ()
    evidence_strength: EvidenceStrength
    confidence: float = Field(ge=0, le=1)
    status: LegalFindingStatus
    review_required: bool
    source_references: tuple[SourceReference, ...] = Field(min_length=1)


class LegalFindings(DomainModel):
    findings: tuple[LegalFinding, ...] = ()
    review_required: bool
    validation_disposition: str
    retry_count: int = Field(ge=0)
    reasoning_summary: str | None = None

