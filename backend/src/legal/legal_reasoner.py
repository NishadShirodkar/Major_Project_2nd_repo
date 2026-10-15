"""Constrained legal reasoning using element evaluation and relation graphs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
import json
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from ..context.case_context import CaseContext
from ..normalization.canonical_models import CanonicalFact
from ..validation.validation_models import ValidationDisposition
from .date_gate import extract_offence_date, filter_references_by_date, select_law
from .evidence_mapper import EvidenceMapper
from .legal_findings import (
    ElementFinding,
    ElementState,
    EvidenceMapping,
    EvidenceStrength,
    LegalFinding,
    LegalFindingStatus,
    LegalFindings,
)
from .legal_rules import Element, LegalReference, LegalReferenceProvider


class LegalReasoningClient(ABC):
    @abstractmethod
    def generate_json(self, prompt: str) -> dict[str, Any]: ...


def eval_element(
    el: Element,
    tagged_facts: dict[str, list[tuple[CanonicalFact, EvidenceMapping]]],
    conflict_paths: set[str],
) -> tuple[ElementState, dict[str, list[EvidenceMapping]]]:
    """Evaluate a single statutory element against tagged investigation facts.
    
    Rules:
    - hits: maps each element fact_tag to matched evidence mappings
    - ok: all tags matched if tag_match == 'all', else at least one tag matched
    - any fact in hits is conflicted -> 'contradicted'
    - el.officer_judgment -> 'officer_review' (NEVER auto 'satisfied')
    - ok -> 'satisfied', else 'unknown'
    """
    hits: dict[str, list[EvidenceMapping]] = {}
    matched_facts: list[CanonicalFact] = []
    
    for tag in el.fact_tags:
        pairs = tagged_facts.get(tag, [])
        hits[tag] = [mapping for _, mapping in pairs]
        matched_facts.extend([fact for fact, _ in pairs])

    present = [t for t, mappings in hits.items() if mappings]
    ok = (len(present) == len(el.fact_tags)) if el.tag_match == "all" else bool(present)

    # Check contradiction / conflict
    for f in matched_facts:
        if f.source_path in conflict_paths or any(cp in f.source_path for cp in conflict_paths):
            return "contradicted", hits

    if not ok:
        return "unknown", hits

    if el.officer_judgment:
        return "officer_review", hits

    return "satisfied", hits


class LegalReasoner:
    def __init__(
        self,
        reference_provider: LegalReferenceProvider,
        client: LegalReasoningClient | None = None,
        *,
        max_attempts: int = 2,
    ) -> None:
        self.reference_provider = reference_provider
        self.client = client
        self.max_attempts = max_attempts
        self.evidence_mapper = EvidenceMapper()

    def reason(self, context: CaseContext) -> LegalFindings:
        # 1. Retrieve references from provider (surfacing any provider errors)
        all_refs = self.reference_provider.references_for(context)

        # 2. Validation block gate
        if context.validation_disposition == ValidationDisposition.FINAL_BLOCKED.value:
            return LegalFindings(
                findings=(),
                review_required=True,
                validation_disposition=context.validation_disposition,
                retry_count=0,
            )

        # 3. Date Gate
        offence_date, date_ambiguous_or_missing = extract_offence_date(context)
        applicable_law = select_law(offence_date)
        if applicable_law is None or date_ambiguous_or_missing:
            # Missing or ambiguous date requires officer review; findings blocked
            return LegalFindings(
                findings=(),
                review_required=True,
                validation_disposition=context.validation_disposition,
                retry_count=0,
                is_draft=getattr(self.reference_provider, "is_draft", False),
                draft_banner=getattr(self.reference_provider, "draft_banner", None),
            )

        # 4. Filter references by date
        valid_refs = filter_references_by_date(all_refs, offence_date) if offence_date else all_refs

        available_evidence = self.evidence_mapper.available(context)
        tag_map = self.evidence_mapper.tag_map(context)
        conflict_paths = {issue.field_path for issue in context.conflicts}
        for c in context.canonical_conflicts:
            conflict_paths.add(c.field_path)

        if self.client is not None:
            return self._reason_with_client(context, valid_refs, available_evidence)

        findings = self._evaluate_all(context, valid_refs, tag_map, conflict_paths, offence_date, applicable_law)

        is_draft = getattr(self.reference_provider, "is_draft", False)
        draft_banner = getattr(self.reference_provider, "draft_banner", None)
        review_required = (
            context.validation_disposition != ValidationDisposition.DRAFT_ALLOWED.value
            or any(item.review_required for item in findings)
            or not findings
            or is_draft
        )

        dataset_status = getattr(getattr(self.reference_provider, "dataset", None), "dataset_status", None)

        return LegalFindings(
            findings=tuple(findings),
            review_required=review_required,
            validation_disposition=context.validation_disposition,
            retry_count=0,
            dataset_status=dataset_status,
            is_draft=is_draft,
            draft_banner=draft_banner,
        )

    def _generate_candidates(
        self,
        context: CaseContext,
        references: tuple[LegalReference, ...],
        present_tags: set[str],
    ) -> list[LegalReference]:
        """Candidate generation: union of FIR sections, trigger_fact_tags, and IPC concordance."""
        fir_section_nums = {
            str(fact.value).strip().removeprefix("BNS:").removeprefix("IPC:").split("(")[0]
            for fact in context.legal_section_references
            if fact.value
        }
        fir_full_keys = {
            str(fact.value).strip()
            for fact in context.legal_section_references
            if fact.value
        }

        candidates: list[LegalReference] = []
        for ref in references:
            # Chargeable only for main findings
            if not ref.chargeable:
                continue

            # 1. Match FIR section
            match_fir = (
                ref.section_number in fir_section_nums
                or ref.key in fir_full_keys
            )

            # 2. Match trigger fact tags
            match_triggers = bool(ref.trigger_fact_tags and any(t in present_tags for t in ref.trigger_fact_tags))

            # 3. Match IPC concordance
            match_ipc = False
            for fir_k in fir_full_keys:
                if any(ipc.casefold() in fir_k.casefold() for ipc in ref.ipc_equivalent):
                    match_ipc = True
                    break

            if match_fir or match_triggers or match_ipc:
                candidates.append(ref)

        # Fallback: if no candidates matched through triggers/FIR, evaluate all chargeable references
        return candidates if candidates else [r for r in references if r.chargeable]

    def _evaluate_all(
        self,
        context: CaseContext,
        references: tuple[LegalReference, ...],
        tag_map: dict[str, list[tuple[CanonicalFact, EvidenceMapping]]],
        conflict_paths: set[str],
        offence_date: date | None,
        applicable_law: str,
    ) -> list[LegalFinding]:
        present_tags = set(tag_map.keys())
        candidates = self._generate_candidates(context, references, present_tags)
        ref_lookup = {r.key: r for r in references}

        # Check section 3(5) applicability
        section_3_5 = ref_lookup.get("BNS:3(5)")
        evaluate_3_5 = bool(section_3_5 and len(context.accused) >= 2)

        # Check mutual exclusion across candidate sections
        mutually_exclusive_pairs: set[frozenset[str]] = set()
        for r in candidates:
            for rel in r.relations:
                if rel.relation == "mutually_exclusive":
                    mutually_exclusive_pairs.add(frozenset([r.key, rel.key]))

        findings: list[LegalFinding] = []
        accused_list = context.accused or [None]

        for accused_entity in accused_list:
            accused_id = accused_entity.id if accused_entity else None
            accused_name = str(accused_entity.name.value) if accused_entity and accused_entity.name else None

            # Evaluate section 3(5) for this accused
            applies_3_5 = False
            if evaluate_3_5 and section_3_5:
                res_3_5 = [
                    eval_element(el, tag_map, conflict_paths)[0]
                    for el in section_3_5.elements
                    if el.required
                ]
                if all(s in {"satisfied", "officer_review"} for s in res_3_5):
                    applies_3_5 = True

            for ref in candidates:
                element_results: list[ElementFinding] = []
                supporting_evidence_set: list[EvidenceMapping] = []
                contradicting_evidence_set: list[EvidenceMapping] = []

                for el in ref.elements:
                    state, hits = eval_element(el, tag_map, conflict_paths)
                    matched_mappings = [m for ms in hits.values() for m in ms]
                    src_refs = tuple(ref for m in matched_mappings for ref in m.source_references)
                    element_results.append(
                        ElementFinding(
                            element_id=el.id,
                            element_type=el.type,
                            description=el.description,
                            state=state,
                            evidence_refs=src_refs,
                            fact_tags=el.fact_tags,
                            hits={k: tuple(m.description for m in v) for k, v in hits.items()},
                            officer_judgment=el.officer_judgment,
                        )
                    )
                    if state in {"satisfied", "officer_review"}:
                        supporting_evidence_set.extend(matched_mappings)
                    elif state == "contradicted":
                        contradicting_evidence_set.extend(matched_mappings)

                # Roll-up status logic per user specification:
                # - Any required element contradicted -> conflicted
                # - Any required element unknown -> insufficient_evidence
                # - All non-officer elements satisfied, officer elements officer_review -> supported with review_required=True
                req_elements = [res for res in element_results if next((el.required for el in ref.elements if el.id == res.element_id), True)]
                has_contradicted = any(res.state == "contradicted" for res in req_elements)
                has_unknown = any(res.state == "unknown" for res in req_elements)
                has_officer_review = any(res.state == "officer_review" for res in req_elements)

                if has_contradicted:
                    status = LegalFindingStatus.CONFLICTED
                    review_required = True
                elif has_unknown:
                    status = LegalFindingStatus.INSUFFICIENT_EVIDENCE
                    review_required = True
                else:
                    # All required elements are satisfied or officer_review
                    status = LegalFindingStatus.SUPPORTED
                    review_required = has_officer_review

                # Deduplicate supporting evidence
                unique_supporting: list[EvidenceMapping] = []
                seen_keys = set()
                for m in supporting_evidence_set:
                    k = (m.source_document_id, m.field_path)
                    if k not in seen_keys:
                        seen_keys.add(k)
                        unique_supporting.append(m)

                # Fallback to general evidence if empty
                if not unique_supporting:
                    unique_supporting = list(self.evidence_mapper.available(context))

                unique_contradicting: list[EvidenceMapping] = []
                for m in contradicting_evidence_set:
                    k = (m.source_document_id, m.field_path)
                    if k not in seen_keys:
                        seen_keys.add(k)
                        unique_contradicting.append(m)

                strength = (
                    EvidenceStrength.HIGH if len(unique_supporting) >= 2
                    else EvidenceStrength.MEDIUM if unique_supporting
                    else EvidenceStrength.LOW
                )

                # Warnings & Suggestions from relations
                warnings: list[str] = []
                suggestions: list[str] = []
                for pair in mutually_exclusive_pairs:
                    if ref.key in pair:
                        other = next(k for k in pair if k != ref.key)
                        if any(c.key == other for c in candidates):
                            warnings.append(
                                f"Mutually exclusive with {other} for the same act and victim. Officer review required to choose."
                            )

                for rel in ref.relations:
                    if rel.relation == "alternative_charge":
                        suggestions.append(f"Alternative charge available: {rel.key}")
                    elif rel.relation == "may_combine_with":
                        suggestions.append(f"May combine with: {rel.key}")

                # Format section title and law
                proposed = f"{ref.section_number}({ref.sub_section})" if ref.sub_section else ref.section_number
                if applicable_law == "IPC" and ref.ipc_equivalent:
                    proposed = f"{ref.ipc_equivalent[0]} (equivalent to {ref.key})"

                read_with = ("BNS:3(5)",) if applies_3_5 else ()

                src_references = tuple(
                    r for m in unique_supporting for r in m.source_references
                )

                findings.append(
                    LegalFinding(
                        legal_reference_id=ref.section_id,
                        section_key=ref.key,
                        law_code=ref.law_code,
                        offence=ref.offence_name,
                        proposed_section=proposed,
                        accused_id=accused_id,
                        accused_name=accused_name,
                        description=ref.description,
                        element_results=tuple(element_results),
                        supporting_evidence=tuple(unique_supporting),
                        contradicting_evidence=tuple(unique_contradicting),
                        evidence_strength=strength,
                        confidence=0.85 if status == LegalFindingStatus.SUPPORTED else 0.4,
                        status=status,
                        review_required=review_required,
                        source_references=src_references,
                        dataset_status=ref.review.status,
                        warnings=tuple(warnings),
                        suggestions=tuple(suggestions),
                        read_with=read_with,
                    )
                )

        return findings

    def _reason_with_client(
        self,
        context: CaseContext,
        references: tuple[LegalReference, ...],
        available: tuple[EvidenceMapping, ...],
    ) -> LegalFindings:
        allowed = {(item.source_document_id, item.field_path) for item in available}
        prompt = json.dumps(
            {
                "context": context.model_dump(mode="json"),
                "legal_references": [item.model_dump(mode="json") for item in references],
                "allowed_evidence": [item.model_dump(mode="json") for item in available],
                "schema": LegalFindings.model_json_schema(),
            },
            default=str,
        )
        for attempt in range(self.max_attempts):
            try:
                result = LegalFindings.model_validate(self.client.generate_json(prompt))
                if result.validation_disposition != context.validation_disposition:
                    raise ValueError("Validation disposition cannot be changed by legal reasoning")
                legal_sections = {(item.section_id, item.section_number) for item in references}
                if any(
                    (item.legal_reference_id, item.proposed_section) not in legal_sections
                    or any((e.source_document_id, e.field_path) not in allowed for e in item.supporting_evidence)
                    for item in result.findings
                ):
                    raise ValueError("Finding uses an unavailable legal section or evidence mapping")
                return result.model_copy(
                    update={
                        "retry_count": attempt,
                        "review_required": (
                            result.review_required
                            or context.validation_disposition != ValidationDisposition.DRAFT_ALLOWED.value
                        ),
                    }
                )
            except (ValidationError, ValueError, KeyError):
                pass
        return LegalFindings(
            findings=(),
            review_required=True,
            validation_disposition=context.validation_disposition,
            retry_count=self.max_attempts,
        )
