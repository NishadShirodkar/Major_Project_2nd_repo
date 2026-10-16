"""Comprehensive tests for Charge-Sheet Review, Completeness, Provenance, and Finalization Engine."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_storage_root
from src.api.schemas.review import AddNoteRequest, CorrectionRequest, DecisionRequest
from src.api.services.case_review_service import CaseReviewService
from src.chargesheet.completeness_reporter import CompletenessReporter
from src.chargesheet.form_if5_schema import (
    ChargeSheetData,
    ChargeSheetField,
    ChargeSheetLegalFinding,
    ChargeSheetReviewItem,
    FieldStatus,
    IF5Row,
    SourceReference,
)
from src.intake.storage_layout import CaseStorageLayout
from src.rendering.if5_renderer import IF5Renderer
from src.review.review_models import ReviewStatus
from src.review.review_service import ReviewLifecycleError


def make_sample_chargesheet(case_id, disposition="draft_allowed", version=1) -> ChargeSheetData:
    doc_id = uuid4()
    s_ref = SourceReference(document_id=doc_id, confidence="high")
    populated = lambda val: ChargeSheetField(
        value=val,
        status=FieldStatus.POPULATED,
        source_references=(s_ref,),
        origin="extracted",
    )
    unavailable = lambda: ChargeSheetField(
        status=FieldStatus.UNAVAILABLE,
        review_required=True,
        origin="unavailable",
    )

    finding = ChargeSheetLegalFinding(
        offence=populated("Voluntarily causing hurt"),
        proposed_section=populated("Section 115 BNS"),
        description=populated("Accused voluntarily caused bodily hurt"),
        status="supported",
        evidence_strength="high",
        review_required=False,
        supporting_evidence=(populated("Medical examination report confirms lacerations"),),
        contradicting_evidence=(),
        ingredient_assessments=(
            {
                "ingredient_name": "hurt",
                "status": "SUPPORTED",
                "supporting_facts": ("Doctor observed 3cm cut",),
                "missing_facts": (),
            },
        ),
        missing_evidence=(),
        reasoning_summary="All statutory ingredients supported by medical certificate.",
        review_warnings=(),
    )

    row = IF5Row(
        serial=1,
        description=populated("Ramesh Kumar, age 32, resident of Panaji"),
        exhibit=ChargeSheetField(value="Exhibit A-1", status=FieldStatus.POPULATED, source_references=(s_ref,)),
    )

    return ChargeSheetData(
        case_id=case_id,
        disposition=disposition,
        version=version,
        case_number=populated("FIR 42/2026"),
        police_station=populated("Panaji Police Station"),
        court=populated("Judicial Magistrate First Class, Panaji"),
        case_summary=populated("On 12/01/2026, an altercation occurred resulting in hurt."),
        detailed_facts=populated("Complainant was assaulted by accused near bus stand."),
        investigation_conducted=populated("Recorded statements of complainant and eye-witnesses.\nSeized weapon of offence."),
        evidence_analysis=populated("Medical reports corroborate the assault narrative."),
        complainants=(row,),
        victims=(row,),
        accused=(row,),
        witnesses=(row,),
        timeline=(row,),
        documentary_evidence=(row,),
        material_evidence=(row,),
        medical_findings=(populated("Lacerated wound on left forearm"),),
        forensic_findings=(unavailable(),),
        vehicle_findings=(unavailable(),),
        legal_sections=(populated("Section 115 BNS"),),
        legal_findings=(finding,),
        conflicts=(),
        missing_information=(),
        annexures=(row,),
        final_opinion=populated("Sufficient evidence exists to prosecute accused under Section 115 BNS."),
        signature=populated("Inspector V. Naik, Investigating Officer"),
    )


class ChargeSheetReviewEngineTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.storage_root = Path(self.temp_dir.name)
        self.case_id = uuid4()
        self.layout = CaseStorageLayout(self.storage_root, self.case_id).ensure_exists()

        # Seed charge sheet v1 on disk
        self.data_v1 = make_sample_chargesheet(self.case_id, version=1)
        draft_dir = self.layout.processed_directory / "chargesheet" / "draft"
        draft_dir.mkdir(parents=True, exist_ok=True)
        v1_data_path = draft_dir / "ChargeSheet_v1_data.json"
        v1_data_path.write_text(json.dumps(self.data_v1.model_dump(mode="json"), indent=2), encoding="utf-8")

        # Render draft PDF
        v1_pdf_path = draft_dir / "ChargeSheet_v1_review.pdf"
        IF5Renderer().render(self.data_v1, v1_pdf_path)

        self.service = CaseReviewService(self.storage_root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_completeness_report_evaluates_correctly(self):
        reporter = CompletenessReporter()
        report = reporter.report(self.data_v1)
        self.assertEqual(len(report.critical_blockers), 0)
        self.assertGreater(report.completeness_score, 0.7)
        self.assertTrue(report.finalization_permitted)

    def test_completeness_report_flags_critical_blockers(self):
        blocked_data = make_sample_chargesheet(self.case_id, disposition="final_blocked")
        reporter = CompletenessReporter()
        report = reporter.report(blocked_data)
        self.assertGreater(len(report.critical_blockers), 0)
        self.assertTrue(any("FINAL_BLOCKED" in b for b in report.critical_blockers))
        self.assertFalse(report.finalization_permitted)

    def test_get_review_data_initial_state(self):
        res = self.service.get_review_data(str(self.case_id))
        self.assertEqual(res.status, ReviewStatus.REVIEW_REQUIRED.value)
        self.assertEqual(res.data_version, 1)
        self.assertTrue(res.can_approve)
        self.assertFalse(res.can_finalize)  # Must be approved before finalization
        self.assertFalse(res.is_finalized)
        self.assertTrue(res.draft_pdf_available)
        self.assertFalse(res.final_pdf_available)

    def test_apply_corrections_increments_version_and_records_provenance(self):
        corr_req = CorrectionRequest(
            reviewer_id="officer_789",
            reviewer_name="Inspector V. Naik",
            comments="Clarified factual description based on supplementary statement.",
            corrections={
                "case_summary": "Updated case summary: altercation occurred at 21:30 hrs.",
                "detailed_facts": "Updated facts: accused brandished a blunt object.",
            },
        )
        res = self.service.apply_corrections(str(self.case_id), corr_req)

        self.assertEqual(res.data_version, 2)
        self.assertIn(2, res.available_versions)
        self.assertEqual(res.status, ReviewStatus.DRAFT.value)  # Reverted to draft for review

        # Check provenance on updated field
        summary_field = res.charge_sheet_data["case_summary"]
        self.assertEqual(summary_field["value"], "Updated case summary: altercation occurred at 21:30 hrs.")
        self.assertEqual(summary_field["origin"], "reviewer_corrected")
        self.assertEqual(summary_field["corrected_by"], "officer_789")
        self.assertIsNotNone(summary_field["original_value"])

        # Check that PDF v2 was rendered
        v2_pdf = self.layout.processed_directory / "chargesheet" / "draft" / "ChargeSheet_v2_review.pdf"
        self.assertTrue(v2_pdf.is_file())

    def test_add_note_appends_to_review(self):
        note_req = AddNoteRequest(
            author_id="legal_analyst_01",
            author_name="Adv. Sharma",
            note_text="Medical certificate has been verified with Goa Medical College records.",
        )
        res = self.service.add_note(str(self.case_id), note_req)
        self.assertEqual(len(res.notes), 1)
        self.assertEqual(res.notes[0]["author_id"], "legal_analyst_01")
        self.assertIn("verified with Goa Medical College", res.notes[0]["note_text"])

    def test_approve_and_finalize_guarded_workflow(self):
        # 1. Approve
        app_req = DecisionRequest(
            decision="approve",
            reviewer_id="sp_north_goa",
            reviewer_name="Superintendent of Police",
            comments="Investigation findings and statutory sections verified.",
        )
        res = self.service.record_decision(str(self.case_id), app_req)
        self.assertEqual(res.status, ReviewStatus.APPROVED.value)
        self.assertTrue(res.can_finalize)

        # 2. Finalize
        fin_req = DecisionRequest(
            decision="finalize",
            reviewer_id="sp_north_goa",
            reviewer_name="Superintendent of Police",
        )
        res_fin = self.service.record_decision(str(self.case_id), fin_req)
        self.assertEqual(res_fin.status, ReviewStatus.FINALIZED.value)
        self.assertTrue(res_fin.is_finalized)
        self.assertTrue(res_fin.final_pdf_available)

        # 3. Final PDF exists on disk
        final_pdf = self.layout.processed_directory / "chargesheet" / "final" / f"ChargeSheet_v1_final.pdf"
        self.assertTrue(final_pdf.is_file())

        # 4. Modifying finalized charge sheet raises ReviewLifecycleError
        corr_req = CorrectionRequest(
            reviewer_id="officer_789",
            corrections={"case_summary": "Attempt to edit finalized record"},
        )
        with self.assertRaises(ReviewLifecycleError):
            self.service.apply_corrections(str(self.case_id), corr_req)

    def test_correction_invalidates_prior_approval(self):
        # Approve v1
        self.service.record_decision(
            str(self.case_id),
            DecisionRequest(decision="approve", reviewer_id="sp_officer", comments="Approved v1"),
        )
        res = self.service.get_review_data(str(self.case_id))
        self.assertEqual(res.status, ReviewStatus.APPROVED.value)

        # Apply correction -> must invalidate approval and revert to draft
        self.service.apply_corrections(
            str(self.case_id),
            CorrectionRequest(
                reviewer_id="investigator_2",
                corrections={"investigation_conducted": "Added forensic ballistic verification."},
            ),
        )
        res_after = self.service.get_review_data(str(self.case_id))
        self.assertEqual(res_after.status, ReviewStatus.DRAFT.value)
        self.assertFalse(res_after.can_finalize)


class ChargeSheetAPITests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.storage_root = Path(self.temp_dir.name)
        self.case_id = uuid4()
        self.layout = CaseStorageLayout(self.storage_root, self.case_id).ensure_exists()

        # Seed charge sheet v1
        self.data_v1 = make_sample_chargesheet(self.case_id, version=1)
        draft_dir = self.layout.processed_directory / "chargesheet" / "draft"
        draft_dir.mkdir(parents=True, exist_ok=True)
        v1_data_path = draft_dir / "ChargeSheet_v1_data.json"
        v1_data_path.write_text(json.dumps(self.data_v1.model_dump(mode="json"), indent=2), encoding="utf-8")
        IF5Renderer().render(self.data_v1, draft_dir / "ChargeSheet_v1_review.pdf")

        # FastAPI app with overridden storage root
        self.app = create_app()
        self.app.dependency_overrides[get_storage_root] = lambda: self.storage_root
        self.client = TestClient(self.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_api_get_review(self):
        response = self.client.get(f"/api/v1/cases/{self.case_id}/review")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["case_id"], str(self.case_id))
        self.assertEqual(body["data_version"], 1)
        self.assertIn("charge_sheet_data", body)
        self.assertIn("completeness_report", body)

    def test_api_corrections_and_history(self):
        payload = {
            "reviewer_id": "officer_101",
            "reviewer_name": "DySP Panaji",
            "comments": "Corrected occurrence location",
            "corrections": {"case_summary": "Incident occurred at Market Square, Panaji."},
        }
        res_corr = self.client.post(f"/api/v1/cases/{self.case_id}/review/corrections", json=payload)
        self.assertEqual(res_corr.status_code, 200)
        self.assertEqual(res_corr.json()["data_version"], 2)

        # Check history
        res_hist = self.client.get(f"/api/v1/cases/{self.case_id}/review/history")
        self.assertEqual(res_hist.status_code, 200)
        hist = res_hist.json()
        self.assertEqual(hist["current_version"], 2)
        self.assertIn(2, hist["available_versions"])
        self.assertTrue(any(e["event_type"] == "correction_applied" for e in hist["events"]))

    def test_api_notes_and_decisions(self):
        # Add note
        note_res = self.client.post(
            f"/api/v1/cases/{self.case_id}/review/notes",
            json={"author_id": "auditor_1", "note_text": "Audit note: all annexures intact."},
        )
        self.assertEqual(note_res.status_code, 200)
        self.assertEqual(len(note_res.json()["notes"]), 1)

        # Approve
        app_res = self.client.post(
            f"/api/v1/cases/{self.case_id}/review/decision",
            json={"decision": "approve", "reviewer_id": "sp_officer", "comments": "Approved"},
        )
        self.assertEqual(app_res.status_code, 200)
        self.assertEqual(app_res.json()["status"], "approved")

        # Finalize
        fin_res = self.client.post(
            f"/api/v1/cases/{self.case_id}/review/decision",
            json={"decision": "finalize", "reviewer_id": "sp_officer"},
        )
        self.assertEqual(fin_res.status_code, 200)
        self.assertEqual(fin_res.json()["status"], "finalized")

        # Download final PDF
        pdf_res = self.client.get(f"/api/v1/cases/{self.case_id}/artifacts/chargesheet_final.pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.headers["content-type"], "application/pdf")
        self.assertGreater(len(pdf_res.content), 500)
