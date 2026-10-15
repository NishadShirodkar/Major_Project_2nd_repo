"""Second-line validation for data assembled before rendering."""

from __future__ import annotations

from ..domain.common import DomainModel
from .form_if5_schema import ChargeSheetData, ChargeSheetField, FieldStatus

NON_CHARGEABLE_SECTIONS = frozenset({
    "BNS:3(5)",
    "BNS:100",
    "BNS:101",
    "BNS:114",
    "BNS:116",
})


class ChargeSheetValidationReport(DomainModel):
    errors: tuple[str, ...] = ()
    review_required: bool = False


class ChargeSheetValidator:
    def validate(self, data: ChargeSheetData, *, final: bool = False) -> ChargeSheetValidationReport:
        fields = [
            data.case_number, data.police_station, data.court, data.case_summary,
            data.detailed_facts, data.investigation_conducted, data.evidence_analysis,
            data.final_opinion, data.signature, *data.medical_findings,
            *data.forensic_findings, *data.vehicle_findings, *data.legal_sections,
            *data.fir_sections_not_supported, *data.applicable_not_in_fir,
        ]
        for rows in (
            data.complainants, data.victims, data.accused, data.witnesses,
            data.timeline, data.documentary_evidence, data.material_evidence,
            data.annexures,
        ):
            fields.extend(field for row in rows for field in (row.description, row.exhibit))

        for finding in data.legal_findings:
            fields.extend((
                finding.offence, finding.proposed_section, finding.description,
                *finding.supporting_evidence, *finding.contradicting_evidence,
            ))

        errors = []
        for field in fields:
            if field.status in {FieldStatus.POPULATED, FieldStatus.REVIEW_REQUIRED} and (not field.value or not field.source_references):
                errors.append("Rendered field lacks a value or source reference.")
            if field.status == FieldStatus.UNAVAILABLE and field.value:
                errors.append("Unavailable field contains an unsupported value.")

        # Legal knowledge graph validation gates
        for finding in data.legal_findings:
            # 1. Reject findings on non-chargeable records
            if finding.section_key in NON_CHARGEABLE_SECTIONS:
                errors.append(f"Finding cites non-chargeable reference '{finding.section_key}'.")

            # 2. Reject draft records in final output
            if (final or data.disposition == "final") and (finding.is_draft or data.is_draft_dataset):
                errors.append(f"Final charge sheet cannot cite draft legal reference '{finding.section_key}'.")

            # 3. Reject supported findings with unconfirmed officer_judgment elements in final output
            if (final or data.disposition == "final") and finding.status == "supported":
                unconfirmed = [
                    el.element_id
                    for el in finding.element_rows
                    if el.officer_judgment and el.state == "officer_review"
                ]
                if unconfirmed:
                    errors.append(
                        f"Finding '{finding.proposed_section.value}' is marked supported but has unconfirmed "
                        f"officer_judgment elements: {unconfirmed}."
                    )

        review_required = any(field.review_required for field in fields) or data.is_draft_dataset
        return ChargeSheetValidationReport(errors=tuple(errors), review_required=review_required)
