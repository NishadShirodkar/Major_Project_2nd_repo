"""Constrained legal reasoning using supplied references and evidence mappings only."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import ValidationError

from ..context.case_context import CaseContext
from ..validation.validation_models import ValidationDisposition
from ..rag.rag_models import RelevanceCategory, RetrievedPassage
from .evidence_mapper import EvidenceMapper
from .legal_findings import (
    EvidenceMapping,
    EvidenceStrength,
    IngredientAssessment,
    IngredientStatus,
    LegalFinding,
    LegalFindingStatus,
    LegalFindings,
)
from .legal_rules import LegalReferenceProvider


class LegalReasoningClient(ABC):
    @abstractmethod
    def generate_json(self, prompt: str) -> dict[str, Any]: ...


class LegalReasoner:
    def __init__(
        self,
        reference_provider: LegalReferenceProvider,
        client: LegalReasoningClient | None = None,
        retriever: Any | None = None,
        *,
        max_attempts: int = 2,
    ) -> None:
        self.reference_provider = reference_provider
        self.client = client
        self.retriever = retriever
        self.max_attempts = max_attempts
        self.evidence_mapper = EvidenceMapper()

    def reason(self, context: CaseContext, retriever: Any | None = None) -> LegalFindings:
        active_retriever = retriever or self.retriever
        available = self.evidence_mapper.available(context)
        references = self.reference_provider.references_for(context)
        if context.validation_disposition == ValidationDisposition.FINAL_BLOCKED.value:
            return LegalFindings(findings=(), review_required=True, validation_disposition=context.validation_disposition, retry_count=0)
        if self.client is not None:
            return self._reason_with_client(context, references, available)
        findings = tuple(self._deterministic_finding(reference, available, context, active_retriever) for reference in references)
        return LegalFindings(findings=findings, review_required=context.validation_disposition != ValidationDisposition.DRAFT_ALLOWED.value or any(item.review_required for item in findings) or not references, validation_disposition=context.validation_disposition, retry_count=0)

    def _deterministic_finding(self, reference, evidence, context, retriever=None):
        ingredient_assessments = []
        missing_evidence = []
        contradicting_mappings = []
        finding_passages: list[RetrievedPassage] = []
        review_warnings: list[str] = []
        retrieval_contradiction = False
        ingredient_contradicted = False
        all_supporting_mappings: list[EvidenceMapping] = []

        # Check for case-wide medical findings indicating non-fatal injury vs fatal
        medical_texts = [str(f.value).casefold() for f in context.medical_findings]
        victim_survived = any(
            any(kw in t for kw in ("simple hurt", "grievous hurt", "laceration", "fracture", "abrasion", "discharged", "treated", "alive", "conscious"))
            for t in medical_texts
        )
        post_mortem_na = any(
            "not applicable" in str(doc.attributes.get("post_mortem", "")).casefold() or
            "not conducted" in str(doc.attributes.get("post_mortem", "")).casefold()
            for doc in context.documents
        ) or any(
            "not applicable" in str(f.value).casefold() or "post-mortem: not applicable" in str(f.value).casefold()
            for f in context.medical_findings
        )
        has_fatal_record = any(
            any(kw in t for kw in ("death", "dead", "deceased", "fatal", "post-mortem conducted", "cause of death"))
            for t in medical_texts
        )

        for element in reference.required_elements:
            elem_folded = element.casefold()

            # Safeguard: Contradiction check for fatal requirement when victim survived
            is_death_ingredient = any(kw in elem_folded for kw in ("death of a human being", "causing the death", "causing death"))
            if is_death_ingredient and (victim_survived or post_mortem_na) and not has_fatal_record:
                ingredient_contradicted = True
                status = IngredientStatus.NOT_ESTABLISHED
                reasoning = (
                    "Contradicted by medical and hospital records: victim sustained non-fatal injuries and "
                    "post-mortem examination is not applicable / not conducted. Essential statutory prerequisite of death is absent."
                )
                med_mapping = next(
                    (m for m in evidence if "medical" in m.field_path.casefold() or "injur" in m.description.casefold()),
                    None
                )
                if med_mapping and med_mapping not in contradicting_mappings:
                    contradicting_mappings.append(med_mapping)
                ingredient_assessments.append(
                    IngredientAssessment(
                        ingredient_name=element,
                        status=status,
                        supporting_evidence_ids=(),
                        reasoning=reasoning,
                        retrieved_passages=(),
                    )
                )
                missing_evidence.append(f"Evidence establishing: {element}")
                review_warnings.append(f"Ingredient '{element}' is contradicted: case records confirm victim survived.")
                continue

            # General ingredient keyword & token matching against available canonical evidence
            elem_tokens = [t.strip(",. ") for t in elem_folded.split() if len(t.strip(",. ")) > 3]
            supporting_for_elem = []
            for m in evidence:
                m_desc = m.description.casefold()
                if elem_folded in m_desc:
                    supporting_for_elem.append(m)
                elif elem_tokens and sum(1 for t in elem_tokens if t in m_desc) >= max(1, len(elem_tokens) // 2):
                    supporting_for_elem.append(m)

            # Query retriever for this ingredient if available
            retrieved_for_elem: list[RetrievedPassage] = []
            contradicting_passages_for_elem: list[RetrievedPassage] = []
            if retriever is not None:
                try:
                    query = f"{reference.offence_name}: {element}"
                    passages = retriever.retrieve(query, top_k=2)
                    for p in passages:
                        retrieved_for_elem.append(p)
                        finding_passages.append(p)
                        if p.relevance_category == RelevanceCategory.CONTRADICTING:
                            contradicting_passages_for_elem.append(p)
                            retrieval_contradiction = True
                            contradicting_mappings.append(
                                EvidenceMapping(
                                    source_document_id=p.document_id,
                                    field_path=f"retrieved_passage:{p.document_name}:p{p.page_number}",
                                    description=f"Contradictory passage in {p.document_name} (p. {p.page_number}): {p.text[:120]}...",
                                    source_references=(p.source_reference,),
                                )
                            )
                except Exception:
                    pass

            # Check if any case conflict explicitly touches supporting evidence for this ingredient
            elem_conflict = False
            for issue in context.conflicts:
                for s_ref in issue.source_references:
                    if any(m.source_document_id == s_ref.document_id for m in supporting_for_elem):
                        elem_conflict = True
                        break

            # Determine ingredient status with strict provenance and anti-hallucination guardrails
            if supporting_for_elem:
                all_supporting_mappings.extend(supporting_for_elem)
                if elem_conflict or contradicting_passages_for_elem:
                    status = IngredientStatus.REQUIRES_REVIEW
                    reasoning = "Corroborating records exist but case or retrieved document contains conflicting statements."
                else:
                    status = IngredientStatus.SUPPORTED
                    reasoning = f"Supported by evidence: {supporting_for_elem[0].description[:100]}"
                    supporting_retrieved = [p for p in retrieved_for_elem if p.relevance_category == RelevanceCategory.SUPPORTING]
                    if supporting_retrieved:
                        reasoning += f". Textually corroborated by {supporting_retrieved[0].document_name} (p. {supporting_retrieved[0].page_number})."
                ingredient_assessments.append(
                    IngredientAssessment(
                        ingredient_name=element,
                        status=status,
                        supporting_evidence_ids=tuple(str(m.source_document_id) for m in supporting_for_elem),
                        reasoning=reasoning,
                        retrieved_passages=tuple(retrieved_for_elem),
                    )
                )
            elif any(p.relevance_category == RelevanceCategory.SUPPORTING for p in retrieved_for_elem):
                # Critical guardrail: Semantic similarity alone NEVER marks an ingredient as established
                supp = next(p for p in retrieved_for_elem if p.relevance_category == RelevanceCategory.SUPPORTING)
                ingredient_assessments.append(
                    IngredientAssessment(
                        ingredient_name=element,
                        status=IngredientStatus.REQUIRES_REVIEW,
                        supporting_evidence_ids=(),
                        reasoning=f"No structured fact recorded. Textual passage retrieved from {supp.document_name} (p. {supp.page_number}) indicates potential corroboration; requires officer verification.",
                        retrieved_passages=tuple(retrieved_for_elem),
                    )
                )
                review_warnings.append(f"Ingredient '{element}' relies on retrieved textual corroboration without canonical fact.")
            else:
                ingredient_assessments.append(
                    IngredientAssessment(
                        ingredient_name=element,
                        status=IngredientStatus.NOT_ESTABLISHED,
                        supporting_evidence_ids=(),
                        reasoning=f"No investigation evidence currently corroborates ingredient '{element}'.",
                        retrieved_passages=tuple(retrieved_for_elem),
                    )
                )
                missing_evidence.append(f"Evidence establishing: {element}")

        # Check scoped conflicts: mark conflicted if an issue relates to this offence or has general case scope
        unique_supporting = list(dict.fromkeys(all_supporting_mappings))
        finding_conflict = False
        for issue in context.conflicts:
            if not issue.source_references or any(term in issue.field_path.casefold() for term in ("evidence", "investigation", "case", reference.section_number.casefold())):
                finding_conflict = True
            else:
                for s_ref in issue.source_references:
                    matching_map = next((m for m in unique_supporting if m.source_document_id == s_ref.document_id), None)
                    if matching_map:
                        finding_conflict = True
                        if matching_map not in contradicting_mappings:
                            contradicting_mappings.append(matching_map)

        num_supported = sum(1 for a in ingredient_assessments if a.status == IngredientStatus.SUPPORTED)
        total_elements = len(reference.required_elements)
        all_supported = (total_elements == 0) or (num_supported == total_elements)

        is_procedural = getattr(reference, "provision_type", "substantive") in ("procedural", "evidentiary")

        if ingredient_contradicted:
            status = LegalFindingStatus.INSUFFICIENT_EVIDENCE
            review_required = True
            confidence = 0.0
            strength = EvidenceStrength.LOW
            review_warnings.append(
                f"Section {reference.section_number} ({reference.offence_name}) cannot be sustained: "
                "essential statutory prerequisite is directly contradicted by investigation evidence."
            )
        elif retrieval_contradiction or finding_conflict:
            status = LegalFindingStatus.CONFLICTED
            review_required = True
            confidence = 0.4
            strength = EvidenceStrength.MEDIUM if len(unique_supporting) >= 1 else EvidenceStrength.LOW
            if retrieval_contradiction:
                review_warnings.append("Retrieved document passage contradicts statutory ingredient(s) of this offence.")
            if finding_conflict:
                review_warnings.append("Evidentiary conflict in case records directly affects this offence.")
        elif all_supported and (unique_supporting or total_elements == 0):
            status = LegalFindingStatus.SUPPORTED
            review_required = False
            confidence = 0.85
            strength = EvidenceStrength.HIGH if len(unique_supporting) >= 2 else EvidenceStrength.MEDIUM
        elif num_supported > 0 or any(a.status == IngredientStatus.REQUIRES_REVIEW for a in ingredient_assessments):
            status = LegalFindingStatus.REVIEW_REQUIRED
            review_required = True
            confidence = 0.5
            strength = EvidenceStrength.MEDIUM if num_supported > 0 else EvidenceStrength.LOW
        else:
            status = LegalFindingStatus.INSUFFICIENT_EVIDENCE
            review_required = True
            confidence = 0.0
            strength = EvidenceStrength.LOW
            review_warnings.append(
                f"Zero statutory ingredients established for Section {reference.section_number} ({reference.offence_name}). "
                "Insufficient evidence to sustain charge."
            )

        # Build specific supporting evidence list without leaking irrelevant case items
        if unique_supporting:
            selected = tuple(unique_supporting)
        elif finding_passages:
            selected = tuple(
                EvidenceMapping(
                    source_document_id=p.document_id,
                    field_path=f"retrieved_passage:{p.document_name}:p{p.page_number}",
                    description=f"Retrieved passage in {p.document_name} (p. {p.page_number}): {p.text[:120]}...",
                    source_references=(p.source_reference,),
                )
                for p in finding_passages
            )
        else:
            # Check if this section is mentioned as an initial allegation in FIR / case metadata
            allegation_maps = [
                m for m in evidence
                if reference.section_number in m.description or "legal_section" in m.field_path
            ]
            if allegation_maps:
                selected = (allegation_maps[0],)
            elif evidence:
                selected = (evidence[0],)
            else:
                selected = self._context_evidence(context)

        statute_name = getattr(reference, "statute", "The Bharatiya Nyaya Sanhita, 2023")
        reasoning_summary = (
            f"Statutory analysis for Section {reference.section_number} ({reference.offence_name}) under {statute_name}: "
            f"{num_supported} of {total_elements} ingredients established. "
            f"Disposition: {status.value.upper()}. Evidence strength: {strength.value.upper()}, Confidence: {confidence:.2f}."
        )

        if missing_evidence:
            review_warnings.append(f"Missing evidence for {len(missing_evidence)} ingredient(s).")
        if is_procedural:
            review_warnings.append(
                f"Statutory provision is {reference.provision_type} (compliance standard), not a substantive penal offence charged against accused."
            )

        return LegalFinding(
            legal_reference_id=reference.section_id,
            offence=reference.offence_name,
            proposed_section=reference.section_number,
            statute=statute_name,
            description=reference.description,
            supporting_evidence=selected,
            contradicting_evidence=tuple(contradicting_mappings),
            ingredient_assessments=tuple(ingredient_assessments),
            retrieved_passages=tuple(finding_passages),
            missing_evidence=tuple(missing_evidence),
            reasoning_summary=reasoning_summary,
            review_warnings=tuple(review_warnings),
            evidence_strength=strength,
            confidence=confidence,
            status=status,
            review_required=review_required,
            source_references=tuple(item for mapping in selected for item in mapping.source_references),
        )

    def _reason_with_client(self, context, references, available) -> LegalFindings:
        allowed = {(item.source_document_id, item.field_path) for item in available}
        prompt = json.dumps({"context": context.model_dump(mode="json"), "legal_references": [item.model_dump(mode="json") for item in references], "allowed_evidence": [item.model_dump(mode="json") for item in available], "schema": LegalFindings.model_json_schema()}, default=str)
        errors = []
        for attempt in range(self.max_attempts):
            try:
                result = LegalFindings.model_validate(self.client.generate_json(prompt))
                if result.validation_disposition != context.validation_disposition: raise ValueError("Validation disposition cannot be changed by legal reasoning")
                legal_sections = {(item.section_id, item.section_number) for item in references}
                if any((item.legal_reference_id, item.proposed_section) not in legal_sections or any((e.source_document_id, e.field_path) not in allowed for e in item.supporting_evidence) for item in result.findings): raise ValueError("Finding uses an unavailable legal section or evidence mapping")
                return result.model_copy(update={"retry_count": attempt, "review_required": result.review_required or context.validation_disposition != ValidationDisposition.DRAFT_ALLOWED.value})
            except (ValidationError, ValueError, KeyError) as exc: errors.append(str(exc))
        return LegalFindings(findings=(), review_required=True, validation_disposition=context.validation_disposition, retry_count=self.max_attempts)

    @staticmethod
    def _context_evidence(context: CaseContext):
        # LegalFinding always needs real evidence; context may still have no eligible evidence.
        mapper = EvidenceMapper().available(context)
        if not mapper: raise ValueError("Legal references cannot yield a finding without evidence mappings")
        return mapper
