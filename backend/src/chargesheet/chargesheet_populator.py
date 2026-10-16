"""Deterministic projection from Phase 9 outputs; this module never infers facts."""

from ..domain.common import SourceReference
from ..context.case_context import CaseContext
from ..legal.legal_findings import LegalFindings, LegalFindingStatus
from ..normalization.canonical_models import CanonicalEvidence, CanonicalFact, CanonicalPerson, CanonicalTimelineEvent
from .form_if5_schema import ChargeSheetData, ChargeSheetField, ChargeSheetLegalFinding, ChargeSheetReviewItem, FieldStatus, IF5Row
from .presentation import document_action_statement, format_inline, format_value, is_temporal_value, label, sentence, unique_lines


class ChargeSheetPopulator:
    def _unavailable(self) -> ChargeSheetField:
        return ChargeSheetField(status=FieldStatus.UNAVAILABLE, review_required=True)

    def _field(self, fact: CanonicalFact | None, review: bool) -> ChargeSheetField:
        if fact is None:
            return self._unavailable()
        rendered = format_value(fact.value)
        if not rendered:
            return self._unavailable()
        return ChargeSheetField(
            value=rendered,
            status=FieldStatus.REVIEW_REQUIRED if review else FieldStatus.POPULATED,
            confidence=fact.confidence,
            source_references=tuple(item.source_reference for item in fact.references),
            review_required=review,
        )

    def _rows(self, facts: tuple[CanonicalFact, ...], review: bool) -> tuple[IF5Row, ...]:
        return tuple(IF5Row(serial=index, description=self._field(fact, review), exhibit=self._unavailable()) for index, fact in enumerate(facts, 1))

    def _joined_field(self, facts: tuple[CanonicalFact, ...], review: bool) -> ChargeSheetField:
        facts = tuple(fact for fact in facts if fact.value is not None and format_value(fact.value) != "Not Available")
        if not facts:
            return self._unavailable()
        references = tuple(dict.fromkeys(reference for fact in facts for reference in (item.source_reference for item in fact.references)))
        confidences = [fact.confidence for fact in facts if fact.confidence is not None]
        return ChargeSheetField(
            value=unique_lines([format_value(fact.value) for fact in facts]),
            status=FieldStatus.REVIEW_REQUIRED if review else FieldStatus.POPULATED,
            confidence=sum(confidences) / len(confidences) if confidences else None,
            source_references=references,
            review_required=review,
        )

    def _person_rows(self, persons: tuple[CanonicalPerson, ...], review: bool) -> tuple[IF5Row, ...]:
        rows = []
        for index, person in enumerate(persons, 1):
            raw_name = format_value(person.name.value)
            clean_name = raw_name.replace("Name:", "").strip() if raw_name else "Unidentified Person"
            facts = [person.name]
            lines = [f"Name: {clean_name}"]

            # Map all available extracted person attributes
            for attr_key, attr_fact in person.attributes.items():
                if attr_fact is not None and attr_fact.value is not None:
                    val_str = format_value(attr_fact.value).strip()
                    if (
                        val_str and
                        val_str.casefold() not in ("none", "n/a", "not available", "witness address", "complainant residence", "unknown", "item 1", "statements", "name:")
                        and not val_str.startswith("Name:")
                    ):
                        facts.append(attr_fact)
                        lines.append(f"{attr_key.replace('_', ' ').capitalize()}: {val_str}")

            desc_field = self._joined_field(tuple(facts), review).model_copy(update={"value": "\n".join(lines)})

            # Exhibit column: Link to source statement, memo, or role record
            all_refs = tuple(dict.fromkeys(ref for f in facts for ref in (item.source_reference for item in f.references)))
            if all_refs:
                first_ref = all_refs[0]
                page_str = f"p. {first_ref.location.page_number}" if first_ref.location and first_ref.location.page_number else "p. 1"
                exhibit_val = f"Source Doc ID: {first_ref.document_id.hex[:8]} ({page_str})"
                exhibit_field = ChargeSheetField(
                    value=exhibit_val,
                    status=FieldStatus.REVIEW_REQUIRED if review else FieldStatus.POPULATED,
                    source_references=all_refs,
                    review_required=review,
                )
            else:
                exhibit_field = ChargeSheetField(status=FieldStatus.NOT_FOUND, review_required=True)

            rows.append(IF5Row(serial=index, description=desc_field, exhibit=exhibit_field))
        return tuple(rows)

    def _timeline_rows(self, events: tuple[CanonicalTimelineEvent, ...], review: bool) -> tuple[IF5Row, ...]:
        rows = []
        serial = 1
        for event in events:
            raw_desc = format_value(event.description.value).strip() if event.description and event.description.value else ""
            if not raw_desc or raw_desc.casefold() in ("name:", "item 1", "statements", "details", "none", "unknown", "n/a"):
                continue
            if raw_desc.startswith("Name:") and len(raw_desc.split()) <= 2:
                continue

            facts = [event.description]
            ts_str = ""
            if event.timestamp and event.timestamp.value is not None:
                facts.append(event.timestamp)
                ts_str = f"[{format_value(event.timestamp.value)}] "

            desc_text = f"{ts_str}{raw_desc}"
            row_review = review or event.status.value == "review_required"
            desc_field = self._joined_field(tuple(facts), row_review).model_copy(update={"value": desc_text})

            all_refs = tuple(dict.fromkeys(ref for f in facts for ref in (item.source_reference for item in f.references)))
            if all_refs:
                first_ref = all_refs[0]
                page_str = f"p. {first_ref.location.page_number}" if first_ref.location and first_ref.location.page_number else "p. 1"
                exhibit_val = f"Record: {first_ref.document_id.hex[:8]} ({page_str})"
                exhibit_field = ChargeSheetField(
                    value=exhibit_val,
                    status=FieldStatus.REVIEW_REQUIRED if row_review else FieldStatus.POPULATED,
                    source_references=all_refs,
                    review_required=row_review,
                )
            else:
                exhibit_field = ChargeSheetField(status=FieldStatus.NOT_FOUND, review_required=True)

            rows.append(IF5Row(serial=serial, description=desc_field, exhibit=exhibit_field))
            serial += 1
        return tuple(rows)

    def _evidence_rows(self, items: tuple[CanonicalEvidence, ...], review: bool) -> tuple[IF5Row, ...]:
        rows = []
        for index, item in enumerate(items, 1):
            facts = [item.description]
            lines = [format_value(item.description.value)]

            for coll in item.collection_details:
                if coll.value is not None:
                    facts.append(coll)
                    lines.append(f"Collection: {format_value(coll.value)}")
            for cust in item.custody_information:
                if cust.value is not None:
                    facts.append(cust)
                    lines.append(f"Custody: {format_value(cust.value)}")
            for attr_k, attr_f in item.attributes.items():
                if attr_f is not None and attr_f.value is not None:
                    facts.append(attr_f)
                    lines.append(f"{attr_k.replace('_', ' ').capitalize()}: {format_value(attr_f.value)}")

            desc_field = self._joined_field(tuple(facts), review).model_copy(update={"value": "\n".join(lines)})

            all_refs = tuple(dict.fromkeys(ref for f in facts for ref in (entry.source_reference for entry in f.references)))
            exhibit_mark = item.attributes.get("exhibit_mark")
            if exhibit_mark and exhibit_mark.value:
                exhibit_val = f"Exhibit Mark: {format_value(exhibit_mark.value)}"
            elif all_refs:
                first_ref = all_refs[0]
                page_str = f"p. {first_ref.location.page_number}" if first_ref.location and first_ref.location.page_number else "p. 1"
                exhibit_val = f"Seizure / Exhibit: {item.evidence_id.hex[:8]} ({page_str})"
            else:
                exhibit_val = f"Exhibit ID: {item.evidence_id.hex[:8]}"

            if not all_refs and item.source_documents:
                all_refs = (SourceReference(document_id=item.source_documents[0]),)

            if all_refs:
                exhibit_field = ChargeSheetField(
                    value=exhibit_val,
                    status=FieldStatus.REVIEW_REQUIRED if review else FieldStatus.POPULATED,
                    source_references=all_refs,
                    review_required=review,
                )
            else:
                exhibit_field = ChargeSheetField(status=FieldStatus.NOT_FOUND, review_required=True)

            rows.append(IF5Row(serial=index, description=desc_field, exhibit=exhibit_field))
        return tuple(rows)

    def _document_rows(self, context: CaseContext, review: bool) -> tuple[IF5Row, ...]:
        rows = []
        for index, document in enumerate(context.documents, 1):
            facts = tuple(item for item in (document.document_type, document.document_id, *document.attributes.values()) if item is not None)
            if not facts:
                continue
            document_type = label(str(document.document_type.value)) if document.document_type else "Source document"
            details = [f"Document ID: {format_inline(document.document_id.value)}"]
            details.extend(
                f"{key.replace('_', ' ').capitalize()}: {format_value(fact.value)}"
                for key, fact in document.attributes.items()
                if fact.value is not None
            )
            field = self._joined_field(facts, review).model_copy(update={"value": f"{document_type}:\n" + "\n".join(details)})
            doc_refs = tuple(dict.fromkeys(ref for fact in facts for ref in (item.source_reference for item in fact.references)))
            if not doc_refs:
                doc_refs = (SourceReference(document_id=document.id),)
            exhibit_field = ChargeSheetField(
                value=f"Annexure A-{index}",
                status=FieldStatus.REVIEW_REQUIRED if review else FieldStatus.POPULATED,
                source_references=doc_refs,
                review_required=review,
            )
            rows.append(IF5Row(serial=index, description=field, exhibit=exhibit_field))
        return tuple(rows)

    def _labelled_field(self, entries: tuple[tuple[str, tuple[CanonicalFact, ...]], ...], review: bool) -> ChargeSheetField:
        facts = tuple(fact for _, group in entries for fact in group)
        if not facts:
            return self._unavailable()
        lines = [f"{heading}: {unique_lines([format_value(fact.value) for fact in group])}" for heading, group in entries if group]
        return self._joined_field(facts, review).model_copy(update={"value": unique_lines(lines)})

    def _case_summary(self, context: CaseContext, review: bool) -> ChargeSheetField:
        facts = [*context.fir_details, *(event.timestamp for event in context.occurrence_details if event.timestamp), *(event.description for event in context.occurrence_details), *(location.name for location in context.locations), *(item.name for item in context.complainants), *(item.name for item in context.accused), *(item.name for item in context.victims), *(item.registration_number for item in context.vehicles)]
        if not facts:
            return self._unavailable()
        occurrence = [format_inline(event.timestamp.value) for event in context.occurrence_details if event.timestamp]
        occurrence.extend(
            format_inline(fact.value) for fact in context.fir_details
            if is_temporal_value(fact.value)
        )
        locations = [format_inline(item.name.value) for item in context.locations]
        people = (("complainant", context.complainants), ("accused", context.accused), ("victim", context.victims))
        lines = []
        if occurrence or locations:
            detail = "The records describe an occurrence"
            if occurrence:
                detail += f" on {'; '.join(dict.fromkeys(occurrence))}"
            if locations:
                detail += f" at {'; '.join(dict.fromkeys(locations))}"
            lines.append(sentence(detail))
        descriptions = [format_inline(event.description.value) for event in context.occurrence_details if event.description.value]
        if descriptions:
            first_sentence = descriptions[0].split(".", 1)[0].strip()
            if first_sentence:
                lines.append(sentence(f"Recorded incident: {first_sentence}"))
        for role, persons in people:
            names = unique_lines([format_inline(person.name.value) for person in persons]).replace("\n", "; ")
            if names:
                lines.append(sentence(f"Recorded {role}{'s' if len(persons) != 1 else ''}: {names}"))
        vehicles = unique_lines([format_inline(item.registration_number.value) for item in context.vehicles]).replace("\n", "; ")
        if vehicles:
            lines.append(sentence(f"Vehicle reference{'s' if len(context.vehicles) != 1 else ''}: {vehicles}"))
        return self._joined_field(tuple(facts), review).model_copy(update={"value": unique_lines(lines)})

    def _investigation_field(self, context: CaseContext, review: bool) -> ChargeSheetField:
        statements, facts = [], []
        for document in context.documents:
            if document.document_type is None:
                continue
            statement = document_action_statement(str(document.document_type.value), {key: fact.value for key, fact in document.attributes.items()})
            if statement:
                statements.append(statement)
                facts.extend((document.document_type, *document.attributes.values()))
        return self._joined_field(tuple(facts), review).model_copy(update={"value": unique_lines(statements)}) if statements else self._joined_field(context.investigation_actions, review)

    def _evidence_analysis(self, context: CaseContext, review: bool) -> ChargeSheetField:
        groups = (("Documentary Evidence", tuple(item.description for item in context.evidence)), ("Physical/Material Evidence", tuple(item.description for item in context.recovered_property)), ("Medical Evidence", context.medical_findings), ("Forensic Evidence", context.forensic_findings), ("Vehicle Evidence", tuple(item.registration_number for item in context.vehicles)), ("Witness Evidence", tuple(item.name for item in context.witnesses)))
        facts = tuple(fact for _, group in groups for fact in group)
        for item in (*context.evidence, *context.recovered_property):
            facts += (*item.collection_details, *item.custody_information)
        if not facts:
            return self._unavailable()
        lines, rendered_evidence = [], set()
        for heading, group in groups:
            values = [line.lstrip("- ").strip() for fact in group for line in format_value(fact.value).splitlines() if line.strip()]
            values = [value for value in values if value not in rendered_evidence]
            if values:
                lines.append(f"{heading}:")
                lines.extend(f"- {sentence(value)}" for value in values)
                rendered_evidence.update(values)
        for item in (*context.evidence, *context.recovered_property):
            details = [format_inline(fact.value) for fact in (*item.collection_details, *item.custody_information) if fact.value is not None]
            if details:
                lines.extend(f"- Collection/custody detail: {sentence(detail)}" for detail in details)
        return self._joined_field(facts, review).model_copy(update={"value": unique_lines(lines)})

    def populate(self, context: CaseContext, findings: LegalFindings) -> ChargeSheetData:
        review = context.validation_disposition != "draft_allowed" or findings.review_required
        complainants = self._person_rows(context.complainants, review)
        victims = self._person_rows(context.victims, review)
        accused = self._person_rows(context.accused, review)
        witnesses = self._person_rows(context.witnesses, review)
        timeline = self._timeline_rows(context.relevant_timeline, review)
        evidence = self._evidence_rows(context.evidence, review)
        recovered = self._evidence_rows(context.recovered_property, review)

        # Distinguish substantive penal offences from procedural/evidentiary compliance standards
        def _is_substantive_offence(f) -> bool:
            statute_cf = getattr(f, "statute", "").casefold()
            if "sakshya" in statute_cf or "suraksha" in statute_cf:
                return False
            warnings_text = " ".join(getattr(f, "review_warnings", ())).casefold()
            if any(term in warnings_text for term in ("procedural", "evidentiary", "compliance standard")):
                return False
            return True

        def _is_contradicted(f) -> bool:
            warnings_text = " ".join(getattr(f, "review_warnings", ())).casefold()
            return "cannot be sustained" in warnings_text or "statutory prerequisite is directly contradicted" in warnings_text

        # 1. Prefer substantive offences that are supported and not contradicted
        substantive_offences = [
            f for f in findings.findings
            if f.status == LegalFindingStatus.SUPPORTED and _is_substantive_offence(f) and not _is_contradicted(f)
        ]
        # 2. If none supported, take review_required or supported offences that are not contradicted
        if not substantive_offences:
            substantive_offences = [
                f for f in findings.findings
                if f.status in (LegalFindingStatus.SUPPORTED, LegalFindingStatus.REVIEW_REQUIRED)
                and _is_substantive_offence(f)
                and not _is_contradicted(f)
            ]
        # 3. If still empty, take non-contradicted substantive offences (even if insufficient_evidence)
        if not substantive_offences:
            substantive_offences = [
                f for f in findings.findings
                if _is_substantive_offence(f) and not _is_contradicted(f)
            ]
        # 4. Fallback to ensure legal_sections is never empty if any substantive offence exists
        if not substantive_offences:
            substantive_offences = [f for f in findings.findings if _is_substantive_offence(f)]
        legal_sections = tuple(self._legal_field(item) for item in substantive_offences)

        finding_rows = tuple(self._legal_finding(item) for item in findings.findings)
        conflict_items = tuple(
            ChargeSheetReviewItem(category="conflict", description=issue.description, source_references=issue.source_references)
            for issue in context.conflicts
        ) + tuple(
            ChargeSheetReviewItem(category="conflict", description=f"Unresolved conflict at {item.field_path}.", source_references=item.source_references)
            for item in context.canonical_conflicts if item.status.value != "resolved"
        )
        missing_items = tuple(
            ChargeSheetReviewItem(category="missing_information", description=item.description, source_references=item.source_references)
            for item in context.missing_information
        ) + tuple(
            ChargeSheetReviewItem(category="missing_information", description=item.description)
            for item in context.canonical_missing_information
        )
        return ChargeSheetData(
            case_id=context.case_id,
            disposition=context.validation_disposition,
            case_number=self._field(context.case_metadata[0] if context.case_metadata else None, review),
            police_station=self._field(context.police_station, review),
            court=self._field(context.court, review),
            case_summary=self._case_summary(context, review),
            detailed_facts=self._joined_field(tuple(event.description for event in context.occurrence_details), review),
            investigation_conducted=self._investigation_field(context, review),
            evidence_analysis=self._evidence_analysis(context, review),
            complainants=complainants, victims=victims, accused=accused, witnesses=witnesses,
            timeline=timeline, documentary_evidence=evidence, material_evidence=recovered,
            medical_findings=tuple(self._field(item, review) for item in context.medical_findings),
            forensic_findings=tuple(self._field(item, review) for item in context.forensic_findings),
            vehicle_findings=tuple(self._field(item.registration_number, review) for item in context.vehicles),
            legal_sections=legal_sections, legal_findings=finding_rows, conflicts=conflict_items, missing_information=missing_items,
            annexures=self._document_rows(context, review),
            final_opinion=self._unavailable(), signature=self._unavailable(),
        )

    def _legal_field(self, finding) -> ChargeSheetField:
        review = finding.review_required or finding.status != LegalFindingStatus.SUPPORTED
        return ChargeSheetField(value=finding.proposed_section or finding.offence, status=FieldStatus.REVIEW_REQUIRED if review else FieldStatus.POPULATED, confidence=finding.confidence, source_references=finding.source_references, review_required=review)

    def _legal_finding(self, finding) -> ChargeSheetLegalFinding:
        review = finding.review_required or finding.status != LegalFindingStatus.SUPPORTED
        evidence = tuple(
            ChargeSheetField(value=format_value(item.description) or "Evidence reference recorded; description unavailable.", status=FieldStatus.REVIEW_REQUIRED if review else FieldStatus.POPULATED, source_references=item.source_references, review_required=review)
            for item in finding.supporting_evidence
        )
        contradicting = tuple(
            ChargeSheetField(value=format_value(item.description) or "Evidence reference recorded; description unavailable.", status=FieldStatus.REVIEW_REQUIRED, source_references=item.source_references, review_required=True)
            for item in finding.contradicting_evidence
        )
        raw_assessments = getattr(finding, "ingredient_assessments", ())
        assessments = tuple(
            a.model_dump(mode="json") if hasattr(a, "model_dump") else a
            for a in raw_assessments
        )
        raw_passages = getattr(finding, "retrieved_passages", ())
        passages = tuple(
            p.model_dump(mode="json") if hasattr(p, "model_dump") else p
            for p in raw_passages
        )
        return ChargeSheetLegalFinding(
            offence=ChargeSheetField(value=finding.offence, status=FieldStatus.REVIEW_REQUIRED if review else FieldStatus.POPULATED, confidence=finding.confidence, source_references=finding.source_references, review_required=review),
            proposed_section=self._legal_field(finding),
            description=ChargeSheetField(value=finding.description, status=FieldStatus.REVIEW_REQUIRED if review else FieldStatus.POPULATED, confidence=finding.confidence, source_references=finding.source_references, review_required=review),
            status=finding.status.value, evidence_strength=finding.evidence_strength.value, review_required=review,
            supporting_evidence=evidence, contradicting_evidence=contradicting,
            ingredient_assessments=assessments,
            retrieved_passages=passages,
            missing_evidence=tuple(getattr(finding, "missing_evidence", ())),
            reasoning_summary=getattr(finding, "reasoning_summary", None),
            review_warnings=tuple(getattr(finding, "review_warnings", ())),
        )

