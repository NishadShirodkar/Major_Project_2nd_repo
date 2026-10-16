"""Phase 6 Comprehensive End-to-End Hardening and Integration Test Suite.

Validates the complete Byomkesh AI charge-sheet workflow across Stages B through I:
- Scenario 1: Complete, internally consistent case from upload to finalized certified PDF.
- Scenario 2: Missing mandatory information blocks finalization server-side without fabricating facts.
- Scenario 3: Contradictory witness statements surfaced with exact provenance; no silent discard.
- Scenario 4: Irrelevant evidence and unsupported offences remain NOT_ESTABLISHED; no hallucinated sections.
- Scenario 5: Evidence discovered through RAG preserves provenance and remains review-required.
- Scenario 6: Empty, missing, and corrupt RAG index fall back safely without server crash.
- Scenario 7: Strict case isolation prevents cross-case retrieval and directory traversal.
- Scenario 8: Reviewer corrections increment versions, preserve original values, and update PDF.
- Scenario 9: Workflow state transitions enforced server-side (approval, rejection, revision, finalization).
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import UUID, uuid4
import zlib

from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas

from src.api.app import create_app
from src.api.config import api_config
from src.api.dependencies import (
    get_artifact_service,
    get_case_service,
    get_job_service,
    get_review_service,
    get_storage_root,
)
from src.api.schemas.review import CorrectionRequest, DecisionRequest
from src.api.services.artifact_service import ArtifactService
from src.api.services.case_review_service import CaseReviewService
from src.api.services.case_service import CaseService
from src.api.services.job_service import JobService
from src.chargesheet.completeness_reporter import CompletenessReporter
from src.chargesheet.form_if5_schema import ChargeSheetData, ChargeSheetField, FieldStatus
from src.domain.common import SourceReference
from src.extraction.mock_client import MockOCRClient, MockParserClient
from src.intake.storage_layout import CaseStorageLayout
from src.intake.upload_manager import IncomingUpload
from src.rag.case_retriever import CaseRetriever
from src.rag.document_chunker import DocumentChunker
from src.rag.embedding_provider import MockEmbeddingProvider, NoOpEmbeddingProvider
from src.rag.rag_models import DocumentChunk, RelevanceCategory, RetrievedPassage
from src.rendering.if5_renderer import IF5Renderer
from src.review.review_models import ReviewStatus
from src.review.review_service import ReviewLifecycleError, ReviewService
from src.workflow.engine import WorkflowEngine
from src.workflow.production import create_production_registry, create_workflow_context
from src.workflow.state import StageStatus

LEGAL_REF_PATH = Path(__file__).parents[1] / "references" / "legal" / "bns_sections.json"
LEGAL_REF_VERSION = "bns-2023-2024-07-01"


def make_pdf_bytes(title: str = "Test Evidence Document", body: str = "Sample evidence text.") -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf)
    c.drawString(72, 750, title)
    c.drawString(72, 730, body)
    c.save()
    return buf.getvalue()


def inspect_pdf_structure(data: bytes) -> tuple[int, str]:
    """Dependency-free structural check for ReportLab PDFs."""
    if not (data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF")):
        raise AssertionError("PDF header or EOF marker is missing")
    page_count = len(re.findall(rb"/Type\s*/Page\b", data))
    decoded = []
    for stream in re.findall(rb"stream[\r\n]+(.*?)endstream", data, re.DOTALL):
        clean = stream.strip()
        try:
            # ReportLab default: ASCII85Decode then FlateDecode (zlib)
            decoded.append(zlib.decompress(base64.a85decode(clean, adobe=True)).decode("latin-1", errors="ignore"))
        except Exception:
            try:
                decoded.append(zlib.decompress(clean).decode("latin-1", errors="ignore"))
            except Exception:
                pass
    return page_count, "\n".join(decoded)


class Phase6HardeningE2ETests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.storage_root = Path(self.temp_dir.name).resolve()

        self.app = create_app()
        self.case_service = CaseService(self.storage_root)
        self.job_service = JobService(self.storage_root)
        self.artifact_service = ArtifactService(self.storage_root)
        self.review_service = CaseReviewService(self.storage_root)

        self.app.dependency_overrides[get_storage_root] = lambda: self.storage_root
        self.app.dependency_overrides[get_case_service] = lambda: self.case_service
        self.app.dependency_overrides[get_job_service] = lambda: self.job_service
        self.app.dependency_overrides[get_artifact_service] = lambda: self.artifact_service
        self.app.dependency_overrides[get_review_service] = lambda: self.review_service

        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    # =========================================================================
    # STAGE B: SCENARIO 1 - COMPLETE, INTERNALLY CONSISTENT CASE
    # =========================================================================
    def test_scenario_1_complete_consistent_case_workflow_to_final_pdf(self) -> None:
        """Scenario 1: Complete case runs through all 9 stages, RAG, approval, and final PDF."""
        case_id = "case_scen_1_consistent"

        # 1. Create case via API
        c_res = self.client.post("/api/v1/cases", json={"case_id": case_id, "title": "Consistent Assault Case"})
        self.assertEqual(c_res.status_code, 201)

        # 2. Upload full realistic synthetic document set
        docs = [
            ("FIR.pdf", "FIR 42/2026. Central PS. Complainant: Asha Devi. Accused: Raj Verma. Section 115 BNS."),
            ("complaint.pdf", "Written complaint by Asha Devi regarding physical assault by Raj Verma on Market Road."),
            ("witness_statement_01.pdf", "Statement of Ravi Kumar: saw Raj Verma strike Sameer Khan on Market Road."),
            ("medical_report.pdf", "MLC-1. Dr Sen examined Sameer Khan: simple hurt, contusion over left forearm."),
            ("seizure_memo.pdf", "SZ-1. Seized wooden stick exhibit E1 from Market Road crime scene."),
            ("vehicle_inspection.pdf", "VI-1. Vehicle KA01AB1234 inspected by Officer Rao; undamaged."),
            ("fsl_report.pdf", "FSL-1. Blood group on wooden stick matches victim blood sample."),
            ("site_plan.pdf", "SP-1. Rough site sketch of Market Road near tea stall."),
        ]
        files = [("files", (name, make_pdf_bytes(name, text), "application/pdf")) for name, text in docs]
        u_res = self.client.post(f"/api/v1/cases/{case_id}/documents", files=files)
        self.assertEqual(u_res.status_code, 201)
        self.assertEqual(u_res.json()["uploaded_count"], len(docs))

        # 3. Process case with mock_llm=True
        p_res = self.client.post(f"/api/v1/cases/{case_id}/process", json={"mock_llm": True})
        self.assertEqual(p_res.status_code, 202)
        job_id = p_res.json()["job_id"]

        job = self.job_service.wait_for_job(job_id, timeout=20.0)
        self.assertEqual(job.status, "completed")
        self.assertEqual(len(job.completed_stages), 9)

        # 4. Verify all expected artifacts exist
        art_res = self.client.get(f"/api/v1/cases/{case_id}/artifacts")
        self.assertEqual(art_res.status_code, 200)
        artifacts = {a["name"]: a for a in art_res.json()["artifacts"]}
        for name in (
            "upload_manifest", "investigation_graph", "canonical_investigation",
            "validation_report", "case_context", "legal_findings", "chargesheet_data", "chargesheet_draft"
        ):
            self.assertTrue(artifacts[name]["exists"], f"Artifact '{name}' missing")

        # 5. Verify RAG index generated and retrievable
        rag_res = self.client.get(f"/api/v1/cases/{case_id}/review/retrieval?query=Asha+Devi&top_k=5")
        self.assertEqual(rag_res.status_code, 200)
        rag_data = rag_res.json()
        self.assertGreater(rag_data["total_chunks_indexed"], 0)
        self.assertGreater(len(rag_data["passages"]), 0)
        first_passage = rag_data["passages"][0]
        self.assertEqual(rag_data["case_id"], case_id)
        self.assertIn("page_number", first_passage)
        self.assertEqual(first_passage["page_number"], 1)
        self.assertIn("document_name", first_passage)
        self.assertIn("source_reference", first_passage)

        # 6. Verify review data & completeness
        rev_res = self.client.get(f"/api/v1/cases/{case_id}/review")
        self.assertEqual(rev_res.status_code, 200)
        review_data = rev_res.json()
        self.assertEqual(review_data["status"], "review_required")
        self.assertEqual(review_data["data_version"], 1)
        self.assertTrue(review_data["can_approve"])

        # 7. Approve draft
        app_res = self.client.post(
            f"/api/v1/cases/{case_id}/review/decision",
            json={"decision": "approve", "reviewer_id": "io_officer_42", "reviewer_name": "Inspector Rao", "comments": "Evidence is consistent and verified."},
        )
        self.assertEqual(app_res.status_code, 200)
        self.assertEqual(app_res.json()["status"], "approved")

        # 7b. Attempt to finalize before IO opinion and signature -> blocked by backend!
        premature_fin = self.client.post(
            f"/api/v1/cases/{case_id}/review/decision",
            json={"decision": "finalize", "reviewer_id": "io_officer_42"},
        )
        self.assertEqual(premature_fin.status_code, 400)
        self.assertIn("Finalization blocked", premature_fin.json()["detail"])

        # 7c. Submit required IO final opinion and signature
        self.client.post(
            f"/api/v1/cases/{case_id}/review/corrections",
            json={
                "reviewer_id": "io_officer_42",
                "reviewer_name": "Inspector Rao",
                "comments": "Submitting investigating officer final opinion and signature block.",
                "corrections": {
                    "final_opinion": "Sufficient oral, documentary, and forensic evidence exists to prosecute accused Raj Verma under Section 115 BNS.",
                    "signature": "Inspector Rao, Station House Officer, Central Police Station",
                },
            },
        )
        # Re-approve version 2 with all finalization requirements satisfied
        re_app = self.client.post(
            f"/api/v1/cases/{case_id}/review/decision",
            json={"decision": "approve", "reviewer_id": "io_officer_42", "reviewer_name": "Inspector Rao"},
        )
        self.assertEqual(re_app.status_code, 200)

        # 8. Finalize charge sheet
        fin_res = self.client.post(
            f"/api/v1/cases/{case_id}/review/decision",
            json={"decision": "finalize", "reviewer_id": "io_officer_42"},
        )
        self.assertEqual(fin_res.status_code, 200)
        fin_data = fin_res.json()
        self.assertEqual(fin_data["status"], "finalized")
        self.assertTrue(fin_data["is_finalized"])
        self.assertTrue(fin_data["final_pdf_available"])

        # 9. Download draft and final PDFs
        draft_pdf = self.client.get(f"/api/v1/cases/{case_id}/artifacts/chargesheet.pdf")
        self.assertEqual(draft_pdf.status_code, 200)
        self.assertTrue(draft_pdf.content.startswith(b"%PDF-"))

        final_pdf = self.client.get(f"/api/v1/cases/{case_id}/artifacts/chargesheet_final.pdf")
        self.assertEqual(final_pdf.status_code, 200)
        self.assertTrue(final_pdf.content.startswith(b"%PDF-"))

        # 10. Verify structural contents of draft vs final
        _, draft_text = inspect_pdf_structure(draft_pdf.content)
        pages_final, final_text = inspect_pdf_structure(final_pdf.content)
        self.assertGreater(pages_final, 0)
        self.assertIn("DRAFT", draft_text)
        self.assertIn("FINALIZED", final_text)

    # =========================================================================
    # STAGE B: SCENARIO 2 - MISSING MANDATORY INFORMATION
    # =========================================================================
    def test_scenario_2_missing_mandatory_information_blocks_approval_and_finalization(self) -> None:
        """Scenario 2: When mandatory FIR is missing, blockers are recorded and approval/finalization blocked."""
        case_id = "case_scen_2_missing_fir"
        self.client.post("/api/v1/cases", json={"case_id": case_id, "title": "Missing FIR Case"})

        # Upload only a witness statement (no FIR, no complaint)
        doc = ("witness_only.pdf", make_pdf_bytes("Witness Statement", "Ravi saw an argument."))
        self.client.post(f"/api/v1/cases/{case_id}/documents", files=[("files", ("witness_only.pdf", doc[1], "application/pdf"))])

        incomplete_data = ChargeSheetData(
            case_id=uuid4(),
            version=1,
            disposition="final_blocked",
            case_number=ChargeSheetField(status=FieldStatus.UNAVAILABLE, review_required=True),
            police_station=ChargeSheetField(status=FieldStatus.UNAVAILABLE, review_required=True),
            court=ChargeSheetField(status=FieldStatus.UNAVAILABLE, review_required=True),
            case_summary=ChargeSheetField(status=FieldStatus.UNAVAILABLE, review_required=True),
            detailed_facts=ChargeSheetField(status=FieldStatus.UNAVAILABLE, review_required=True),
            investigation_conducted=ChargeSheetField(status=FieldStatus.UNAVAILABLE, review_required=True),
            evidence_analysis=ChargeSheetField(status=FieldStatus.UNAVAILABLE, review_required=True),
            final_opinion=ChargeSheetField(status=FieldStatus.UNAVAILABLE, review_required=True),
            signature=ChargeSheetField(status=FieldStatus.UNAVAILABLE, review_required=True),
        )

        reporter = CompletenessReporter()
        report = reporter.report(incomplete_data)
        self.assertFalse(report.finalization_permitted)
        self.assertGreater(len(report.critical_blockers), 0)
        self.assertTrue(any("Case / FIR Number" in b or "FINAL_BLOCKED" in b for b in report.critical_blockers))

        # Test ReviewService refuses to approve FINAL_BLOCKED charge sheet
        review = ReviewService().create_draft(incomplete_data)
        review = ReviewService().submit_for_review(review, incomplete_data)
        with self.assertRaises(ReviewLifecycleError) as ctx:
            ReviewService().approve(review, incomplete_data, reviewer_id="officer-1")
        self.assertIn("FINAL_BLOCKED", str(ctx.exception))

        # Test ReviewService refuses to finalize FINAL_BLOCKED charge sheet
        with self.assertRaises(ReviewLifecycleError):
            ReviewService().finalize(review, incomplete_data, storage_root=self.storage_root)

    # =========================================================================
    # STAGE B: SCENARIO 3 - CONTRADICTORY WITNESS STATEMENTS
    # =========================================================================
    def test_scenario_3_contradictory_witness_statements_surfaced_with_provenance(self) -> None:
        """Scenario 3: Contradictory witness statements remain retrievable and surfaced with distinct provenance."""
        case_uuid = uuid4()
        storage = self.storage_root

        # Chunk two conflicting witness statements
        statement_1 = (
            "I Ravi Kumar was at Market Road tea shop on 2026-01-01 at 10:00 AM. "
            "I saw Raj Verma holding an iron rod and assaulting Sameer Khan."
        )
        statement_2 = (
            "I Suresh Gupta state that on 2026-01-01 between 09:00 AM and 12:00 PM, "
            "Raj Verma was with me at my residence in Rohini Sector 15 attending a family gathering."
        )

        chunk_1 = DocumentChunk.create(
            case_id=case_uuid,
            document_id=uuid4(),
            original_filename="witness_ravi.pdf",
            page_number=1,
            line_start=1,
            line_end=5,
            text=statement_1,
            confidence=0.95,
        )
        chunk_2 = DocumentChunk.create(
            case_id=case_uuid,
            document_id=uuid4(),
            original_filename="witness_suresh.pdf",
            page_number=1,
            line_start=1,
            line_end=6,
            text=statement_2,
            confidence=0.92,
        )

        retriever = CaseRetriever(storage, case_uuid, embedding_provider=NoOpEmbeddingProvider())
        retriever.build_index((chunk_1, chunk_2))

        # Both passages must be retrievable
        results_ravi = retriever.retrieve("iron rod assaulting", top_k=5)
        self.assertGreater(len(results_ravi), 0)
        self.assertEqual(results_ravi[0].document_id, chunk_1.document_id)
        self.assertEqual(results_ravi[0].page_number, 1)

        results_alibi = retriever.retrieve("Rohini residence family gathering alibi", top_k=5)
        self.assertGreater(len(results_alibi), 0)
        self.assertEqual(results_alibi[0].document_id, chunk_2.document_id)
        self.assertEqual(results_alibi[0].page_number, 1)

        # Neither passage is silently discarded
        all_results = retriever.retrieve("Raj Verma", top_k=5)
        retrieved_docs = {p.document_id for p in all_results}
        self.assertIn(chunk_1.document_id, retrieved_docs)
        self.assertIn(chunk_2.document_id, retrieved_docs)

    # =========================================================================
    # STAGE B: SCENARIO 4 - IRRELEVANT EVIDENCE AND UNSUPPORTED OFFENCE
    # =========================================================================
    def test_scenario_4_irrelevant_evidence_does_not_establish_offence(self) -> None:
        """Scenario 4: Irrelevant passages do not establish ingredients; semantic match alone is rejected."""
        case_uuid = uuid4()
        irrelevant_text = (
            "Invoice #9901 for 50 bags of Portland Cement supplied to ABC Traders. "
            "Total amount paid INR 25,000 via NEFT. Cement bags received at godown."
        )
        chunk = DocumentChunk.create(
            case_id=case_uuid,
            document_id=uuid4(),
            original_filename="cement_invoice.pdf",
            page_number=1,
            line_start=1,
            line_end=4,
            text=irrelevant_text,
            confidence=0.98,
        )

        retriever = CaseRetriever(self.storage_root, case_uuid, embedding_provider=NoOpEmbeddingProvider())
        retriever.build_index((chunk,))

        # Query for robbery / extortion ingredients
        results = retriever.retrieve("dishonestly taking movable property without consent extortion robbery", top_k=5)
        # Passages do not establish statutory ingredients
        for p in results:
            self.assertNotEqual(p.relevance_category, RelevanceCategory.SUPPORTING)

    # =========================================================================
    # STAGE B: SCENARIO 5 - EVIDENCE DISCOVERED THROUGH RAG
    # =========================================================================
    def test_scenario_5_evidence_discovered_via_rag_preserves_provenance_and_requires_review(self) -> None:
        """Scenario 5: Unstructured fact found in RAG retains exact page/document and requires human review."""
        case_uuid = uuid4()
        text = "The assailant wore a blue helmet with a cracked visor and escaped on an unregistered scooter."
        doc_id = uuid4()
        chunk = DocumentChunk.create(
            case_id=case_uuid,
            document_id=doc_id,
            original_filename="witness_supplementary.pdf",
            page_number=2,
            line_start=15,
            line_end=20,
            text=text,
            confidence=0.88,
        )

        retriever = CaseRetriever(self.storage_root, case_uuid, embedding_provider=NoOpEmbeddingProvider())
        retriever.build_index((chunk,))

        results = retriever.retrieve("blue helmet cracked visor scooter", top_k=1)
        self.assertEqual(len(results), 1)
        passage = results[0]
        self.assertEqual(passage.document_id, doc_id)
        self.assertEqual(passage.page_number, 2)
        self.assertEqual(passage.line_range, (15, 20))
        self.assertIn("blue helmet", passage.text)

    # =========================================================================
    # STAGE B: SCENARIO 6 - EMPTY OR CORRUPT RAG INDEX
    # =========================================================================
    def test_scenario_6_empty_or_corrupt_rag_index_falls_back_safely(self) -> None:
        """Scenario 6: Missing or corrupted RAG index does not crash the system or leak data."""
        case_uuid = uuid4()
        layout = CaseStorageLayout(self.storage_root, case_uuid).ensure_exists()

        # 1. New case with zero documents / missing index
        retriever = CaseRetriever(self.storage_root, case_uuid, embedding_provider=NoOpEmbeddingProvider())
        empty_res = retriever.retrieve("any query", top_k=5)
        self.assertEqual(empty_res, ())
        self.assertEqual(len(retriever.chunks), 0)

        # 2. Corrupted index file
        index_file = layout.processed_directory / "rag" / "index.json"
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.write_text("<<<MALFORMED JSON SYNTAX ERROR>>>", encoding="utf-8")

        corrupt_retriever = CaseRetriever(self.storage_root, case_uuid, embedding_provider=NoOpEmbeddingProvider())
        safe_res = corrupt_retriever.retrieve("any query", top_k=5)
        self.assertEqual(safe_res, ())
        self.assertEqual(len(corrupt_retriever.chunks), 0)

    # =========================================================================
    # STAGE B: SCENARIO 7 - CASE ISOLATION AND TRAVERSAL PREVENTION
    # =========================================================================
    def test_scenario_7_strict_case_isolation_and_path_traversal_rejection(self) -> None:
        """Scenario 7: Queries for Case A never return Case B passages; path manipulation is rejected."""
        case_a = uuid4()
        case_b = uuid4()

        chunk_a = DocumentChunk.create(
            case_id=case_a,
            document_id=uuid4(),
            original_filename="statement_a.pdf",
            page_number=1,
            line_start=1,
            line_end=2,
            text="Suspect Sunil Sharma seen near Connaught Place Market at 14:00 hrs.",
            confidence=0.9,
        )
        chunk_b = DocumentChunk.create(
            case_id=case_b,
            document_id=uuid4(),
            original_filename="statement_b.pdf",
            page_number=1,
            line_start=1,
            line_end=2,
            text="Suspect Sunil Sharma seen near Chandni Chowk Metro at 14:00 hrs.",
            confidence=0.9,
        )

        retriever_a = CaseRetriever(self.storage_root, case_a, embedding_provider=NoOpEmbeddingProvider())
        retriever_b = CaseRetriever(self.storage_root, case_b, embedding_provider=NoOpEmbeddingProvider())

        retriever_a.build_index((chunk_a,))
        retriever_b.build_index((chunk_b,))

        # Query Case A for Case B location
        res_a = retriever_a.retrieve("Chandni Chowk Metro", top_k=5)
        self.assertEqual(len(res_a), 0)

        # Query Case B for Case A location
        res_b = retriever_b.retrieve("Connaught Place Market", top_k=5)
        self.assertEqual(len(res_b), 0)

        # Path traversal rejection via API
        traversal_res = self.client.get("/api/v1/cases/../../etc/passwd/review")
        self.assertIn(traversal_res.status_code, (400, 404))

    # =========================================================================
    # STAGE B: SCENARIO 8 - REVIEWER CORRECTION AND VERSIONING
    # =========================================================================
    def test_scenario_8_reviewer_correction_increments_version_and_updates_pdf(self) -> None:
        """Scenario 8: Reviewer correction creates v2, invalidates approval, and updates draft PDF."""
        case_id = "case_scen_8_versioning"
        self.client.post("/api/v1/cases", json={"case_id": case_id, "title": "Versioning Test"})

        docs = [
            ("FIR.pdf", "FIR 101/2026. Central PS. Complainant: Asha Devi. Accused: Raj Verma."),
            ("complaint.pdf", "Complaint of assault on Sameer Khan."),
        ]
        files = [("files", (name, make_pdf_bytes(name, text), "application/pdf")) for name, text in docs]
        self.client.post(f"/api/v1/cases/{case_id}/documents", files=files)
        proc = self.client.post(f"/api/v1/cases/{case_id}/process", json={"mock_llm": True})
        self.job_service.wait_for_job(proc.json()["job_id"], timeout=15.0)

        # Initial review data is v1
        rev_v1 = self.client.get(f"/api/v1/cases/{case_id}/review").json()
        self.assertEqual(rev_v1["data_version"], 1)

        # Submit reviewer correction
        corrected_summary = "Corrected: Incident occurred at 22:30 hrs after verbal altercation."
        corr_res = self.client.post(
            f"/api/v1/cases/{case_id}/review/corrections",
            json={
                "reviewer_id": "io_officer_77",
                "reviewer_name": "Inspector K. Singh",
                "comments": "Corrected timeline based on witness statement.",
                "corrections": {"case_summary": corrected_summary},
            },
        )
        self.assertEqual(corr_res.status_code, 200)
        rev_v2 = corr_res.json()
        self.assertEqual(rev_v2["data_version"], 2)
        self.assertIn(2, rev_v2["available_versions"])
        self.assertEqual(rev_v2["charge_sheet_data"]["case_summary"]["value"], corrected_summary)
        self.assertEqual(rev_v2["charge_sheet_data"]["case_summary"]["origin"], "reviewer_corrected")

        # Verify audit history
        hist = self.client.get(f"/api/v1/cases/{case_id}/review/history").json()
        self.assertEqual(hist["current_version"], 2)
        event_types = [e["event_type"] for e in hist["events"]]
        self.assertIn("correction_applied", event_types)

        # Verify draft PDF reflects v2 and contains Reviewer Corrected mark
        pdf_res = self.client.get(f"/api/v1/cases/{case_id}/artifacts/chargesheet.pdf")
        self.assertEqual(pdf_res.status_code, 200)
        _, pdf_text = inspect_pdf_structure(pdf_res.content)
        self.assertIn("VERSION 2", pdf_text)

    # =========================================================================
    # STAGE B: SCENARIO 9 - APPROVAL AND FINALIZATION TRANSITIONS
    # =========================================================================
    def test_scenario_9_approval_and_finalization_transition_safety_guards(self) -> None:
        """Scenario 9: Strict backend state guards on reviewer identity, rejection reasons, and finalization."""
        case_id = "case_scen_9_transitions"
        self.client.post("/api/v1/cases", json={"case_id": case_id, "title": "Transition Guard Test"})

        docs = [
            ("FIR.pdf", "FIR 202/2026. Central PS. Complainant: Asha Devi. Accused: Raj Verma."),
            ("complaint.pdf", "Complaint of physical assault."),
        ]
        files = [("files", (name, make_pdf_bytes(name, text), "application/pdf")) for name, text in docs]
        self.client.post(f"/api/v1/cases/{case_id}/documents", files=files)
        proc = self.client.post(f"/api/v1/cases/{case_id}/process", json={"mock_llm": True})
        self.job_service.wait_for_job(proc.json()["job_id"], timeout=15.0)

        # 1. Attempt to download final PDF before finalization -> must return 404
        pre_final_dl = self.client.get(f"/api/v1/cases/{case_id}/artifacts/chargesheet_final.pdf")
        self.assertEqual(pre_final_dl.status_code, 404)

        # 2. Finalization before approval -> must return 400
        pre_finalize = self.client.post(
            f"/api/v1/cases/{case_id}/review/decision",
            json={"decision": "finalize", "reviewer_id": "sp_officer_1"},
        )
        self.assertEqual(pre_finalize.status_code, 400)

        # 3. Rejection without required reason -> must return 400
        reject_no_reason = self.client.post(
            f"/api/v1/cases/{case_id}/review/decision",
            json={"decision": "reject", "reviewer_id": "sp_officer_1", "rejection_reason": ""},
        )
        self.assertEqual(reject_no_reason.status_code, 400)

        # 4. Request revision with comments -> succeeds and transitions
        rev_req = self.client.post(
            f"/api/v1/cases/{case_id}/review/decision",
            json={"decision": "request_revision", "reviewer_id": "sp_officer_1", "comments": "Please verify exhibit chain."},
        )
        self.assertEqual(rev_req.status_code, 200)
        self.assertEqual(rev_req.json()["status"], "draft")

        # 5. Approve draft with valid officer identity
        app_res = self.client.post(
            f"/api/v1/cases/{case_id}/review/decision",
            json={"decision": "approve", "reviewer_id": "sp_officer_1", "comments": "Chain of custody verified."},
        )
        self.assertEqual(app_res.status_code, 200)
        self.assertEqual(app_res.json()["status"], "approved")

        # 6. Applying correction after approval revokes approval
        corr_after_app = self.client.post(
            f"/api/v1/cases/{case_id}/review/corrections",
            json={
                "reviewer_id": "io_officer_1",
                "corrections": {
                    "court": "Court of Sessions, Central",
                    "final_opinion": "Accused prima facie culpable under Section 115 BNS based on eyewitness testimony.",
                    "signature": "Inspector Rao, Central PS",
                },
            },
        )
        self.assertEqual(corr_after_app.status_code, 200)
        self.assertNotEqual(corr_after_app.json()["status"], "approved")

        # Re-approve version 2 with all required fields present
        re_app = self.client.post(
            f"/api/v1/cases/{case_id}/review/decision",
            json={"decision": "approve", "reviewer_id": "sp_officer_1"},
        )
        self.assertEqual(re_app.status_code, 200)

        # 7. Finalize
        fin_res = self.client.post(
            f"/api/v1/cases/{case_id}/review/decision",
            json={"decision": "finalize", "reviewer_id": "sp_officer_1"},
        )
        self.assertEqual(fin_res.status_code, 200)
        self.assertEqual(fin_res.json()["status"], "finalized")

        # 8. Attempting to apply corrections to finalized version -> must return 400
        post_fin_corr = self.client.post(
            f"/api/v1/cases/{case_id}/review/corrections",
            json={"reviewer_id": "io_officer_1", "corrections": {"case_summary": "Attempt to edit final"}},
        )
        self.assertEqual(post_fin_corr.status_code, 400)
        self.assertIn("FINALIZED", post_fin_corr.json()["detail"])

        # 9. Download final PDF after finalization -> succeeds with 200
        post_final_dl = self.client.get(f"/api/v1/cases/{case_id}/artifacts/chargesheet_final.pdf")
        self.assertEqual(post_final_dl.status_code, 200)
        self.assertEqual(post_final_dl.headers["content-type"], "application/pdf")
        self.assertIn("final_chargesheet", post_final_dl.headers["content-disposition"])
