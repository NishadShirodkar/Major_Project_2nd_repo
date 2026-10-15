"""Typed, review-oriented legal recommendation models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field

from ..domain.common import DomainModel, SourceReference

ElementState = Literal["satisfied", "contradicted", "officer_review", "unknown"]


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
    tag: str | None = None


class ElementFinding(DomainModel):
    element_id: str
    element_type: str = ""
    description: str = ""
    state: ElementState
    evidence_refs: tuple[SourceReference, ...] = ()
    fact_tags: tuple[str, ...] = ()
    hits: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    officer_judgment: bool = False


class LegalFinding(DomainModel):
    finding_id: UUID = Field(default_factory=uuid4)
    legal_reference_id: UUID
    section_key: str = ""
    law_code: str = "BNS"
    offence: str
    proposed_section: str | None = None
    accused_id: UUID | None = None
    accused_name: str | None = None
    description: str
    element_results: tuple[ElementFinding, ...] = ()
    supporting_evidence: tuple[EvidenceMapping, ...] = Field(min_length=1)
    contradicting_evidence: tuple[EvidenceMapping, ...] = ()
    evidence_strength: EvidenceStrength
    confidence: float = Field(ge=0, le=1)
    status: LegalFindingStatus
    review_required: bool
    source_references: tuple[SourceReference, ...] = Field(min_length=1)
    dataset_status: str | None = None
    warnings: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()
    read_with: tuple[str, ...] = ()


class LegalFindings(DomainModel):
    findings: tuple[LegalFinding, ...] = ()
    review_required: bool
    validation_disposition: str
    retry_count: int = Field(ge=0)
    dataset_status: str | None = None
    is_draft: bool = False
    draft_banner: str | None = None
