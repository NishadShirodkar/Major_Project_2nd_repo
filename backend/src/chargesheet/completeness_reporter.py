"""Structured charge-sheet completeness and statutory readiness reporting."""

from __future__ import annotations

from pydantic import Field

from ..domain.common import DomainModel
from .form_if5_schema import ChargeSheetData, FieldStatus


class ChargeSheetCompletenessReport(DomainModel):
    """Auditable metric breakdown separating critical blockers from advisory warnings."""

    completeness_score: float = Field(ge=0.0, le=1.0)
    total_core_fields: int = Field(ge=1)
    populated_fields_count: int = Field(ge=0)
    critical_blockers: tuple[str, ...] = ()
    advisory_warnings: tuple[str, ...] = ()
    missing_required_fields: tuple[str, ...] = ()
    missing_conditional_fields: tuple[str, ...] = ()
    fields_requiring_human_input: tuple[str, ...] = ()
    unresolved_contradictions: tuple[str, ...] = ()
    finalization_permitted: bool = False


class CompletenessReporter:
    """Calculates granular statutory completeness without concealing critical omissions."""

    def report(self, data: ChargeSheetData, *, is_finalization_target: bool = False) -> ChargeSheetCompletenessReport:
        return self.evaluate(data, is_finalization_target=is_finalization_target)

    def evaluate(self, data: ChargeSheetData, *, is_finalization_target: bool = False) -> ChargeSheetCompletenessReport:
        critical_blockers: list[str] = []
        advisory_warnings: list[str] = []
        missing_required: list[str] = []
        missing_conditional: list[str] = []
        human_input_needed: list[str] = []
        contradictions: list[str] = []

        # 1. Check disposition blockers
        if data.disposition == "final_blocked":
            critical_blockers.append("Evidence validation disposition is FINAL_BLOCKED. Investigation fails mandatory legal checks.")

        # 2. Check conflicts
        if data.conflicts:
            for item in data.conflicts:
                desc = f"Conflict in {item.category}: {item.description}"
                contradictions.append(desc)
                # Severe evidentiary contradictions block finalization
                if "fatal" in desc.lower() or "contradict" in desc.lower() or "mismatch" in desc.lower():
                    critical_blockers.append(f"Unresolved evidentiary contradiction: {item.description}")
                else:
                    advisory_warnings.append(f"Pending factual dispute: {item.description}")

        # Core mandatory fields check
        core_checks = [
            ("Case / FIR Number", data.case_number, True),
            ("Police Station", data.police_station, True),
            ("Jurisdictional Court", data.court, True),
            ("Case Summary Narrative", data.case_summary, True),
            ("Detailed Facts of Occurrence", data.detailed_facts, True),
            ("Investigation Steps Conducted", data.investigation_conducted, True),
            ("Evidence Analysis", data.evidence_analysis, True),
            ("Applicable Legal Sections", data.legal_sections, True),
            ("Complainant / Informant Identity", data.complainants, True),
            ("Accused Person Details", data.accused, True),
            ("Investigating Officer Final Opinion", data.final_opinion, is_finalization_target),
            ("Officer Signature Block", data.signature, is_finalization_target),
        ]

        populated_count = 0
        total_fields = len(core_checks)

        for label, target, is_mandatory in core_checks:
            is_populated = False

            if isinstance(target, tuple):
                # Row tuples or field tuples
                if target:
                    # Check first row
                    first = target[0]
                    if hasattr(first, "description"):
                        is_populated = first.description.status in {FieldStatus.POPULATED, FieldStatus.REVIEW_REQUIRED, FieldStatus.REVIEWER_CORRECTED} and bool(first.description.value)
                    elif hasattr(first, "status"):
                        is_populated = first.status in {FieldStatus.POPULATED, FieldStatus.REVIEW_REQUIRED, FieldStatus.REVIEWER_CORRECTED} and bool(first.value)
            elif hasattr(target, "status"):
                is_populated = target.status in {FieldStatus.POPULATED, FieldStatus.REVIEW_REQUIRED, FieldStatus.REVIEWER_CORRECTED} and bool(target.value)

            if is_populated:
                populated_count += 1
            else:
                if is_mandatory:
                    missing_required.append(label)
                    critical_blockers.append(f"Mandatory charge-sheet field missing: {label}")
                else:
                    advisory_warnings.append(f"Field pending completion: {label}")

        # Fields requiring human input
        if data.final_opinion.status == FieldStatus.UNAVAILABLE or not data.final_opinion.value:
            human_input_needed.append("Final Opinion of Investigating Officer (requires supervisory or IO statement)")
        if data.signature.status == FieldStatus.UNAVAILABLE or not data.signature.value:
            human_input_needed.append("Investigating Officer Signature & Designation")

        # Conditional checks
        # Vehicle inspection conditional on vehicle reference
        has_vehicles = bool(data.vehicle_findings and any(v.value for v in data.vehicle_findings))
        if has_vehicles:
            # Check documentary evidence for vehicle inspection report
            has_vi_doc = any(
                "vehicle inspection" in row.description.rendered.lower()
                for row in data.documentary_evidence
            )
            if not has_vi_doc:
                missing_conditional.append("Vehicle Inspection Report (applicable because vehicle was involved)")
                advisory_warnings.append("Vehicle reference present but Motor Vehicle Inspector report not attached.")

        # Medical report conditional on victim or bodily injury
        has_hurt = any("115" in (s.value or "") or "hurt" in (s.value or "").lower() for s in data.legal_sections)
        if has_hurt and not data.medical_findings:
            missing_conditional.append("Medico-Legal Certificate / Injury Report (applicable for offence of hurt)")
            advisory_warnings.append("Offence of causing hurt alleged but no medical finding records attached.")

        score = round(populated_count / total_fields, 2)
        finalization_permitted = (len(critical_blockers) == 0 and data.disposition != "final_blocked")

        return ChargeSheetCompletenessReport(
            completeness_score=score,
            total_core_fields=total_fields,
            populated_fields_count=populated_count,
            critical_blockers=tuple(critical_blockers),
            advisory_warnings=tuple(advisory_warnings),
            missing_required_fields=tuple(missing_required),
            missing_conditional_fields=tuple(missing_conditional),
            fields_requiring_human_input=tuple(human_input_needed),
            unresolved_contradictions=tuple(contradictions),
            finalization_permitted=finalization_permitted,
        )
