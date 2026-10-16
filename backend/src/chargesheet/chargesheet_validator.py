"""Second-line validation for data assembled before rendering."""

from __future__ import annotations

from ..domain.common import DomainModel, SourceReference
from .form_if5_schema import ChargeSheetData, ChargeSheetField, FieldStatus


class ChargeSheetIntegrityIssue(DomainModel):
    issue_type: str
    severity: str  # "error" | "warning"
    field_path: str
    description: str
    source_references: tuple[SourceReference, ...] = ()
    recommended_action: str


class ChargeSheetValidationReport(DomainModel):
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    issues: tuple[ChargeSheetIntegrityIssue, ...] = ()
    review_required: bool = False


class ChargeSheetValidator:
    _PARSER_ARTIFACTS = (
        "item 1",
        "statements",
        "name:",
        "witness address",
        "complainant residence",
        "recovered evidentiary exhibit",
        "placeholder",
    )

    def validate(self, data: ChargeSheetData) -> ChargeSheetValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        issues: list[ChargeSheetIntegrityIssue] = []

        fields: list[tuple[str, ChargeSheetField]] = [
            ("case_number", data.case_number),
            ("police_station", data.police_station),
            ("court", data.court),
            ("case_summary", data.case_summary),
            ("detailed_facts", data.detailed_facts),
            ("investigation_conducted", data.investigation_conducted),
            ("evidence_analysis", data.evidence_analysis),
            ("final_opinion", data.final_opinion),
            ("signature", data.signature),
            *[(f"medical_findings[{i}]", f) for i, f in enumerate(data.medical_findings)],
            *[(f"forensic_findings[{i}]", f) for i, f in enumerate(data.forensic_findings)],
            *[(f"vehicle_findings[{i}]", f) for i, f in enumerate(data.vehicle_findings)],
            *[(f"legal_sections[{i}]", f) for i, f in enumerate(data.legal_sections)],
        ]

        for section_name, rows in (
            ("complainants", data.complainants),
            ("victims", data.victims),
            ("accused", data.accused),
            ("witnesses", data.witnesses),
            ("timeline", data.timeline),
            ("documentary_evidence", data.documentary_evidence),
            ("material_evidence", data.material_evidence),
            ("annexures", data.annexures),
        ):
            for row in rows:
                fields.append((f"{section_name}[{row.serial}].description", row.description))
                fields.append((f"{section_name}[{row.serial}].exhibit", row.exhibit))

        for finding in data.legal_findings:
            fields.extend([
                (f"legal_finding[{finding.offence.rendered}].offence", finding.offence),
                (f"legal_finding[{finding.offence.rendered}].proposed_section", finding.proposed_section),
                (f"legal_finding[{finding.offence.rendered}].description", finding.description),
                *[(f"legal_finding[{finding.offence.rendered}].supporting[{i}]", f) for i, f in enumerate(finding.supporting_evidence)],
                *[(f"legal_finding[{finding.offence.rendered}].contradicting[{i}]", f) for i, f in enumerate(finding.contradicting_evidence)],
            ])

        for path, field in fields:
            # 1. Provenance check
            if field.status in {FieldStatus.POPULATED, FieldStatus.REVIEW_REQUIRED} and (not field.value or not field.source_references):
                err = f"Rendered field at {path} lacks a value or source reference."
                errors.append(err)
                issues.append(ChargeSheetIntegrityIssue(
                    issue_type="missing_provenance",
                    severity="error",
                    field_path=path,
                    description=err,
                    source_references=field.source_references,
                    recommended_action="Ensure extraction maps source document and page number to this fact.",
                ))

            # 2. Unavailable field with unsupported value
            if field.status == FieldStatus.UNAVAILABLE and field.value:
                err = f"Unavailable field at {path} contains an unsupported value."
                errors.append(err)
                issues.append(ChargeSheetIntegrityIssue(
                    issue_type="invalid_unavailable_value",
                    severity="error",
                    field_path=path,
                    description=err,
                    recommended_action="Clear value or mark field status as populated/review_required with provenance.",
                ))

            # 3. Parser artifact / placeholder detection
            if field.value and field.status == FieldStatus.POPULATED:
                val_lower = field.value.strip().casefold()
                if any(val_lower == artifact or val_lower.startswith(f"{artifact} ") for artifact in self._PARSER_ARTIFACTS):
                    warn = f"Field at {path} contains potential parser placeholder artifact: '{field.value[:40]}'."
                    warnings.append(warn)
                    issues.append(ChargeSheetIntegrityIssue(
                        issue_type="parser_artifact",
                        severity="warning",
                        field_path=path,
                        description=warn,
                        source_references=field.source_references,
                        recommended_action="Verify authentic extracted value from uploaded evidence or mark as not found.",
                    ))

        # 4. Legal reasoning integrity check
        applicable_sections = {f.value for f in data.legal_sections if f.value}
        for finding in data.legal_findings:
            sec_num = finding.proposed_section.value
            # Check for contradicted or unestablished ingredients presented as supported
            if finding.status == "supported":
                assessments = getattr(finding, "ingredient_assessments", ())
                for a in assessments:
                    st = a.get("status") if isinstance(a, dict) else getattr(a, "status", None)
                    if st in ("not_established", "contradicted"):
                        err = f"Legal finding for {sec_num} is marked 'supported' but ingredient is '{st}'."
                        errors.append(err)
                        issues.append(ChargeSheetIntegrityIssue(
                            issue_type="unsupported_legal_ingredient",
                            severity="error",
                            field_path=f"legal_findings[{sec_num}]",
                            description=err,
                            recommended_action="Do not present finding as supported when statutory ingredients are absent.",
                        ))

            # Check if overview applicable sections includes an insufficient/conflicted finding
            if sec_num in applicable_sections and finding.status in ("insufficient_evidence", "conflicted"):
                warn = f"Overview applicable sections includes Section {sec_num} which has status '{finding.status}'."
                warnings.append(warn)
                issues.append(ChargeSheetIntegrityIssue(
                    issue_type="legal_overview_mismatch",
                    severity="warning",
                    field_path="legal_sections",
                    description=warn,
                    recommended_action="Review whether this section should be framed or dropped based on investigation findings.",
                ))

        review_required = bool(errors) or bool(warnings) or any(f.review_required for _, f in fields)
        return ChargeSheetValidationReport(
            errors=tuple(errors),
            warnings=tuple(warnings),
            issues=tuple(issues),
            review_required=review_required,
        )
