"""Builds the finite evidence allow-list and tag-based mapping used by legal reasoning."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from ..context.case_context import CaseContext
from ..normalization.canonical_models import CanonicalFact
from .legal_findings import EvidenceMapping, LegalFinding


class EvidenceMapper:
    """Builds the allow-list and maps tags to facts and source references."""

    def _extract_facts(self, context: CaseContext) -> list[CanonicalFact]:
        facts: list[CanonicalFact] = []
        facts.extend(context.medical_findings)
        facts.extend(context.forensic_findings)
        facts.extend(context.legal_section_references)
        for p in context.accused:
            facts.append(p.name)
        for item in context.evidence:
            facts.append(item.description)
        for item in context.recovered_property:
            facts.append(item.description)
        for v in context.vehicles:
            facts.append(v.registration_number)
        for event in context.occurrence_details:
            facts.append(event.description)
        for event in context.relevant_timeline:
            facts.append(event.description)
        for doc in context.documents:
            facts.extend(doc.attributes.values())
        return facts

    def available(self, context: CaseContext) -> tuple[EvidenceMapping, ...]:
        """Finite allow-list of all evidence available in this case."""
        mappings: list[EvidenceMapping] = []
        for fact in self._extract_facts(context):
            if not fact.source_document_ids or not fact.references:
                continue
            doc_id = fact.source_document_ids[0]
            desc = str(fact.value or "")
            src_refs = tuple(item.source_reference for item in fact.references)
            for tag in (fact.tags or (None,)):
                mappings.append(
                    EvidenceMapping(
                        source_document_id=doc_id,
                        field_path=fact.source_path,
                        description=desc,
                        source_references=src_refs,
                        tag=tag,
                    )
                )
        return tuple(mappings)

    def tag_map(self, context: CaseContext) -> dict[str, list[tuple[CanonicalFact, EvidenceMapping]]]:
        """Index facts and evidence mappings by fact tag."""
        result: dict[str, list[tuple[CanonicalFact, EvidenceMapping]]] = {}
        for fact in self._extract_facts(context):
            if not fact.source_document_ids or not fact.references:
                continue
            mapping = EvidenceMapping(
                source_document_id=fact.source_document_ids[0],
                field_path=fact.source_path,
                description=str(fact.value or ""),
                source_references=tuple(item.source_reference for item in fact.references),
            )
            for tag in fact.tags:
                result.setdefault(tag, []).append((fact, mapping))
        return result

    @staticmethod
    def key_for_element(section_key: str, accused_id: UUID | None, element_id: str) -> str:
        accused_str = str(accused_id) if accused_id else "global"
        return f"{section_key}::{accused_str}::{element_id}"

    def build_structured_mapping(
        self,
        findings: tuple[LegalFinding, ...],
    ) -> dict[str, list[dict[str, Any]]]:
        """Builds evidence_mapping.json keyed by (section_key, accused_id, element_id)."""
        mapping: dict[str, list[dict[str, Any]]] = {}
        for f in findings:
            for el in f.element_results:
                k = self.key_for_element(f.section_key, f.accused_id, el.element_id)
                evidence_list = []
                for mapping_item in f.supporting_evidence:
                    evidence_list.append(mapping_item.model_dump(mode="json"))
                mapping[k] = evidence_list
        return mapping
