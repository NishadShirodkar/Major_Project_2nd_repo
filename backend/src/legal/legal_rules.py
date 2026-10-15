"""Controlled, versioned legal references used by legal reasoning."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from enum import StrEnum
import json
from pathlib import Path
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator

from ..context.case_context import CaseContext
from ..domain.common import DomainModel, SourceReference

ElementType = Literal["act", "result", "causation", "mens_rea", "circumstance", "status", "instrument"]
RelationType = Literal[
    "defined_by", "defines", "simple_form", "aggravated_form",
    "mutually_exclusive", "alternative_charge", "may_combine_with"
]
LegalKind = Literal["offence", "definition", "general_principle"]
ReviewStatus = Literal["draft", "in_review", "verified", "rejected"]

INVERSE_RELATIONS: dict[str, str] = {
    "defines": "defined_by",
    "defined_by": "defines",
    "simple_form": "aggravated_form",
    "aggravated_form": "simple_form",
    "mutually_exclusive": "mutually_exclusive",
    "alternative_charge": "alternative_charge",
    "may_combine_with": "may_combine_with",
}


class LegalReferenceConfigurationError(ValueError):
    """Raised when production legal-reference data is absent, malformed, or mismatched."""


class LegalJurisdiction(StrEnum):
    INDIA = "IN"


class LegalReferenceSource(DomainModel):
    publisher: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    uri: str = Field(min_length=1)


class Element(DomainModel):
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    fact_tags: tuple[str, ...] = ()
    tag_match: Literal["any", "all"] = "any"
    required: bool = True
    officer_judgment: bool = False


class Relation(DomainModel):
    key: str = Field(min_length=1)
    relation: str = Field(min_length=1)


class ReviewInfo(DomainModel):
    status: ReviewStatus = "draft"
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    pending_fields: tuple[str, ...] = ()
    notes: str | None = None


class LegalReferenceLaw(DomainModel):
    law_code: str
    title: str
    act: str
    in_force_from: date
    replaces: str


class LegalReference(DomainModel):
    section_id: UUID
    key: str = Field(min_length=1)
    law_code: str = Field(min_length=1)
    section_number: str = Field(min_length=1)
    sub_section: str | None = None
    offence_name: str = Field(min_length=1)
    kind: LegalKind = "offence"
    chargeable: bool = True
    description: str = Field(min_length=1)
    official_text_excerpt: str | None = None
    required_elements: tuple[str, ...] = ()
    elements: tuple[Element, ...] = ()
    relations: tuple[Relation, ...] = ()
    ipc_equivalent: tuple[str, ...] = ()
    trigger_fact_tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    modelling_notes: tuple[str, ...] = ()
    punishment: dict[str, Any] | None = None
    procedure: dict[str, Any] | None = None
    jurisdiction: LegalJurisdiction = LegalJurisdiction.INDIA
    effective_from: date
    effective_to: date | None = None
    source: LegalReferenceSource
    version: str = Field(min_length=1)
    review: ReviewInfo = Field(default_factory=ReviewInfo)
    source_reference: SourceReference

    @model_validator(mode="after")
    def effective_range_is_valid(self) -> "LegalReference":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        return self


class LegalReferenceDataset(DomainModel):
    schema_version: str = "2.0"
    version: str = Field(min_length=1)
    law: LegalReferenceLaw | None = None
    effective_date_semantics: str | None = None
    dataset_status: str | None = None
    element_types: tuple[str, ...] = ()
    relation_types: dict[str, str] = Field(default_factory=dict)
    fact_tag_vocabulary: dict[str, str] = Field(default_factory=dict)
    references: tuple[LegalReference, ...] = ()
    all_references: tuple[LegalReference, ...] = ()

    @model_validator(mode="after")
    def records_match_dataset_version(self) -> "LegalReferenceDataset":
        records = self.all_references or self.references
        if any(reference.version != self.version for reference in records):
            raise ValueError("Every legal reference must match the dataset version")
        return self


def validate_dataset_integrity(payload: dict[str, Any], records: tuple[LegalReference, ...]) -> None:
    """Rigorous load-time validation against the legal dataset constraints."""
    # 1. Unique keys
    keys = [r.key for r in records]
    if len(keys) != len(set(keys)):
        duplicates = {k for k in keys if keys.count(k) > 1}
        raise LegalReferenceConfigurationError(f"Duplicate reference keys found: {duplicates}")

    key_map = {r.key: r for r in records}
    vocab = set(payload.get("fact_tag_vocabulary", {}).keys())

    for r in records:
        element_ids = {el.id for el in r.elements}

        # 2. Every required_elements ID exists in elements
        for req in r.required_elements:
            if req not in element_ids:
                raise LegalReferenceConfigurationError(
                    f"Section '{r.key}' requires element '{req}' which is not defined in elements"
                )

        # 3. Every fact_tag is in fact_tag_vocabulary
        if vocab:
            for el in r.elements:
                for tag in el.fact_tags:
                    if tag not in vocab:
                        raise LegalReferenceConfigurationError(
                            f"Section '{r.key}' element '{el.id}' contains unknown fact tag '{tag}'"
                        )
                # 6. Non-officer elements have at least one tag
                if not el.officer_judgment and not el.fact_tags:
                    raise LegalReferenceConfigurationError(
                        f"Section '{r.key}' element '{el.id}' is non-officer but has no fact tags"
                    )

            for tag in r.trigger_fact_tags:
                if tag not in vocab:
                    raise LegalReferenceConfigurationError(
                        f"Section '{r.key}' trigger tag '{tag}' is not in vocabulary"
                    )

        # 4. Every relations.key exists in dataset
        for rel in r.relations:
            if rel.key not in key_map:
                raise LegalReferenceConfigurationError(
                    f"Section '{r.key}' relation target '{rel.key}' does not exist in dataset"
                )

            # 5. Inverse relations present
            target = key_map[rel.key]
            expected_inverse = INVERSE_RELATIONS.get(rel.relation)
            if expected_inverse:
                target_inverses = [tr.relation for tr in target.relations if tr.key == r.key]
                if expected_inverse not in target_inverses:
                    raise LegalReferenceConfigurationError(
                        f"Missing inverse relation: '{r.key}' -> '{rel.key}' ({rel.relation}) "
                        f"requires '{rel.key}' -> '{r.key}' ({expected_inverse}), but found {target_inverses}"
                    )


class LegalReferenceProvider(ABC):
    @abstractmethod
    def references_for(self, context: CaseContext) -> tuple[LegalReference, ...]: ...


class FixtureLegalReferenceProvider(LegalReferenceProvider):
    """Test-only deterministic provider; production composition never selects it."""

    def __init__(self, references: tuple[LegalReference, ...] = ()) -> None:
        self.references = references

    def references_for(self, context: CaseContext) -> tuple[LegalReference, ...]:
        return self.references

    def lookup(self, identifier: str) -> LegalReference | None:
        return next(
            (
                reference
                for reference in self.references
                if reference.key == identifier or reference.section_number == identifier
            ),
            None,
        )


class LocalLegalReferenceProvider(LegalReferenceProvider):
    """Loads only a validated, version-pinned local reference dataset."""

    def __init__(
        self,
        dataset: LegalReferenceDataset,
        *,
        source_path: Path,
        allow_draft: bool = False,
    ) -> None:
        self.dataset = dataset
        self.source_path = source_path
        self.allow_draft = allow_draft

    @classmethod
    def load(
        cls,
        path: Path | None,
        expected_version: str | None,
        *,
        allow_draft: bool = False,
    ) -> "LocalLegalReferenceProvider":
        if path is None or not str(path).strip():
            raise LegalReferenceConfigurationError("LEGAL_REFERENCE_PATH is required for production legal reasoning")
        if not expected_version:
            raise LegalReferenceConfigurationError("LEGAL_REFERENCE_VERSION is required for production legal reasoning")
        if not path.is_file():
            raise LegalReferenceConfigurationError(f"Configured legal reference dataset was not found: {path}")

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_refs = payload.get("references", [])
            records: list[LegalReference] = []
            for item in raw_refs:
                controlled = dict(item)
                section_id = UUID(str(controlled["section_id"]))
                controlled["source_reference"] = SourceReference(
                    document_id=uuid5(NAMESPACE_URL, f"byomkesh-legal-reference:{section_id}:{controlled['version']}")
                )
                records.append(LegalReference.model_validate(controlled))

            all_records = tuple(records)
            validate_dataset_integrity(payload, all_records)

            # Verified-only gate
            filtered_records = tuple(
                r for r in all_records if allow_draft or r.review.status == "verified"
            )

            law_info = LegalReferenceLaw.model_validate(payload["law"]) if "law" in payload else None
            dataset = LegalReferenceDataset(
                schema_version=payload.get("schema_version", "2.0"),
                version=payload["version"],
                law=law_info,
                effective_date_semantics=payload.get("effective_date_semantics"),
                dataset_status=payload.get("dataset_status"),
                element_types=tuple(payload.get("element_types", ())),
                relation_types=dict(payload.get("relation_types", {})),
                fact_tag_vocabulary=dict(payload.get("fact_tag_vocabulary", {})),
                references=filtered_records,
                all_references=all_records,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LegalReferenceConfigurationError(f"Legal reference dataset is invalid: {exc}") from exc

        if dataset.version != expected_version:
            raise LegalReferenceConfigurationError(
                f"Legal reference version mismatch: configured '{expected_version}', dataset '{dataset.version}'"
            )

        return cls(dataset, source_path=path, allow_draft=allow_draft)

    @property
    def all_references(self) -> tuple[LegalReference, ...]:
        return self.dataset.all_references or self.dataset.references

    @property
    def is_draft(self) -> bool:
        return any(r.review.status != "verified" for r in self.dataset.references)

    @property
    def draft_banner(self) -> str | None:
        if self.is_draft:
            return "WARNING: Legal reference dataset contains unverified DRAFT records. Output is strictly for review."
        return None

    def references_for(self, context: CaseContext) -> tuple[LegalReference, ...]:
        return self.dataset.references

    def lookup(self, identifier: str) -> LegalReference | None:
        return next(
            (
                reference
                for reference in self.all_references
                if reference.key == identifier or reference.section_number == identifier
            ),
            None,
        )
