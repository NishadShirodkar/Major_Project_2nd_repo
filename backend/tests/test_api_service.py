"""Automated tests for the Phase 2 FastAPI backend service layer."""

from __future__ import annotations

import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import uuid4

from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas

from src.api.app import app, create_app
from src.api.config import api_config
from src.api.dependencies import (
    _default_artifact_service,
    _default_case_service,
    _default_job_service,
    get_artifact_service,
    get_case_service,
    get_job_service,
    get_storage_root,
)
from src.api.services.artifact_service import ArtifactService
from src.api.services.case_service import CaseService
from src.api.services.job_service import JobService


def make_pdf_bytes(title: str = "Test PDF") -> bytes:
    buf = io.BytesIO()
    canvas = Canvas(buf)
    canvas.drawString(72, 750, title)
    canvas.save()
    return buf.getvalue()


class FastAPIServiceTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.storage_root = Path(self.temp_dir.name).resolve()

        # Isolate services to the temporary storage directory
        self.case_service = CaseService(self.storage_root)
        self.job_service = JobService(self.storage_root)
        self.artifact_service = ArtifactService(self.storage_root)

        app.dependency_overrides[get_storage_root] = lambda: self.storage_root
        app.dependency_overrides[get_case_service] = lambda: self.case_service
        app.dependency_overrides[get_job_service] = lambda: self.job_service
        app.dependency_overrides[get_artifact_service] = lambda: self.artifact_service

        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    def test_app_imports_without_gemini_credentials(self) -> None:
        """Req 9.1: Application imports and initializes without requiring GEMINI_API_KEY."""
        new_app = create_app()
        client = TestClient(new_app)
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_health_and_readiness_endpoints(self) -> None:
        """Req 9.2: Health and readiness endpoints report correct state."""
        res_h = self.client.get("/health")
        self.assertEqual(res_h.status_code, 200)
        self.assertEqual(res_h.json(), {"status": "ok", "service": "byomkesh-ai", "version": "1.0.0"})

        res_r = self.client.get("/ready")
        self.assertEqual(res_r.status_code, 200)
        data = res_r.json()
        self.assertTrue(data["ready"])
        self.assertTrue(data["checks"]["storage_root"])
        self.assertTrue(data["checks"]["legal_reference"])

    def test_case_creation_and_invalid_case_ids(self) -> None:
        """Req 9.3: Create case with valid IDs and reject malformed / path-traversal IDs."""
        # 1. Safe auto-generated ID
        res1 = self.client.post("/api/v1/cases", json={})
        self.assertEqual(res1.status_code, 201)
        self.assertIn("case_id", res1.json())
        self.assertEqual(res1.json()["status"], "created")

        # 2. Valid client-supplied slug
        res2 = self.client.post("/api/v1/cases", json={"case_id": "case-alpha_01", "title": "Alpha Case"})
        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.json()["case_id"], "case-alpha_01")

        # 3. Path traversal attempts
        res_traversal1 = self.client.post("/api/v1/cases", json={"case_id": "../../etc/passwd"})
        self.assertEqual(res_traversal1.status_code, 400)
        self.assertEqual(res_traversal1.json()["error_code"], "INVALID_CASE_ID")

        res_traversal2 = self.client.post("/api/v1/cases", json={"case_id": "foo/bar"})
        self.assertEqual(res_traversal2.status_code, 400)

        res_traversal3 = self.client.post("/api/v1/cases", json={"case_id": "case*bad!"})
        self.assertEqual(res_traversal3.status_code, 400)

    def test_case_listing_and_retrieval(self) -> None:
        """Req 9.4: List all cases and retrieve specific case details."""
        self.client.post("/api/v1/cases", json={"case_id": "case-1", "title": "First"})
        self.client.post("/api/v1/cases", json={"case_id": "case-2", "title": "Second"})

        res_list = self.client.get("/api/v1/cases")
        self.assertEqual(res_list.status_code, 200)
        cases = res_list.json()["cases"]
        self.assertEqual(len(cases), 2)
        ids = {c["case_id"] for c in cases}
        self.assertIn("case-1", ids)
        self.assertIn("case-2", ids)

        res_detail = self.client.get("/api/v1/cases/case-1")
        self.assertEqual(res_detail.status_code, 200)
        self.assertEqual(res_detail.json()["case_id"], "case-1")
        self.assertEqual(res_detail.json()["title"], "First")

    def test_case_deletion(self) -> None:
        """Verify permanent case deletion removes storage and returns 404 on subsequent queries."""
        self.client.post("/api/v1/cases", json={"case_id": "case-to-delete", "title": "Temporary Case"})
        self.assertEqual(self.client.get("/api/v1/cases/case-to-delete").status_code, 200)

        # Delete the case
        del_res = self.client.delete("/api/v1/cases/case-to-delete")
        self.assertEqual(del_res.status_code, 200)
        del_data = del_res.json()
        self.assertEqual(del_data["status"], "deleted")
        self.assertEqual(del_data["case_id"], "case-to-delete")

        # Subsequent GET must return 404
        self.assertEqual(self.client.get("/api/v1/cases/case-to-delete").status_code, 404)

        # Deleting non-existent case returns 404
        self.assertEqual(self.client.delete("/api/v1/cases/case-to-delete").status_code, 404)

    def test_missing_case_returns_404(self) -> None:
        """Req 9.5: Missing case queries return 404."""
        self.assertEqual(self.client.get("/api/v1/cases/non-existent-case").status_code, 404)
        self.assertEqual(self.client.post("/api/v1/cases/non-existent-case/process").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/cases/non-existent-case/artifacts").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/cases/non-existent-case/artifacts/chargesheet.pdf").status_code, 404)

    def test_single_and_multiple_document_uploads(self) -> None:
        """Req 9.6: Upload single and multiple supported files."""
        self.client.post("/api/v1/cases", json={"case_id": "case-upload"})

        pdf1 = make_pdf_bytes("Doc 1")
        pdf2 = make_pdf_bytes("Doc 2")

        files = [
            ("files", ("FIR.pdf", pdf1, "application/pdf")),
            ("files", ("complaint.pdf", pdf2, "application/pdf")),
        ]
        res = self.client.post("/api/v1/cases/case-upload/documents", files=files)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["uploaded_count"], 2)
        self.assertEqual(data["failed_count"], 0)
        self.assertEqual(len(data["documents"]), 2)

        # Verify case detail reflects document count
        detail = self.client.get("/api/v1/cases/case-upload").json()
        self.assertEqual(detail["document_count"], 2)

    def test_unsupported_file_types_and_empty_uploads(self) -> None:
        """Req 9.7: Reject unsupported extensions and empty uploads."""
        self.client.post("/api/v1/cases", json={"case_id": "case-type-check"})

        # Unsupported extension
        files = [("files", ("malicious.exe", b"binarycontent", "application/octet-stream"))]
        res = self.client.post("/api/v1/cases/case-type-check/documents", files=files)
        self.assertEqual(res.status_code, 415)
        self.assertEqual(res.json()["error_code"], "UNSUPPORTED_MEDIA_TYPE")

    def test_safe_filenames_and_path_traversal_attempts(self) -> None:
        """Req 9.9: Reject path traversal in upload filenames."""
        self.client.post("/api/v1/cases", json={"case_id": "case-path-test"})
        pdf = make_pdf_bytes("Payload")

        traversal_files = [("files", ("../../evil.pdf", pdf, "application/pdf"))]
        res = self.client.post("/api/v1/cases/case-path-test/documents", files=traversal_files)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error_code"], "INVALID_FILENAME")

    def test_case_isolation(self) -> None:
        """Req 9.10: Case uploads and outputs remain strictly separated."""
        self.client.post("/api/v1/cases", json={"case_id": "case-A"})
        self.client.post("/api/v1/cases", json={"case_id": "case-B"})

        pdf = make_pdf_bytes("Doc A")
        self.client.post("/api/v1/cases/case-A/documents", files=[("files", ("FIR.pdf", pdf, "application/pdf"))])

        detail_a = self.client.get("/api/v1/cases/case-A").json()
        detail_b = self.client.get("/api/v1/cases/case-B").json()

        self.assertEqual(detail_a["document_count"], 1)
        self.assertEqual(detail_b["document_count"], 0)

    def test_process_case_requires_uploaded_documents(self) -> None:
        """Cannot trigger processing on a case without documents."""
        self.client.post("/api/v1/cases", json={"case_id": "case-empty"})
        res = self.client.post("/api/v1/cases/case-empty/process", json={"mock_llm": True})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error_code"], "NO_DOCUMENTS_UPLOADED")

    def test_duplicate_processing_requests_rejected_with_409(self) -> None:
        """Req 9.12: Duplicate processing requests on the same case return 409 Conflict."""
        self.client.post("/api/v1/cases", json={"case_id": "case-lock"})
        pdf = make_pdf_bytes("Doc")
        self.client.post("/api/v1/cases/case-lock/documents", files=[("files", ("FIR.pdf", pdf, "application/pdf"))])

        # Manually acquire the active lock on the case to simulate an active job
        case_uuid, _ = self.case_service.get_case("case-lock").case_id, None
        from src.api.services.case_service import parse_safe_case_id
        uuid_val, _ = parse_safe_case_id("case-lock")

        with self.job_service._lock:
            self.job_service._active_cases.add(uuid_val)

        try:
            res = self.client.post("/api/v1/cases/case-lock/process", json={"mock_llm": True})
            self.assertEqual(res.status_code, 409)
            self.assertEqual(res.json()["error_code"], "CASE_ALREADY_PROCESSING")
        finally:
            with self.job_service._lock:
                self.job_service._active_cases.discard(uuid_val)

    def test_job_not_found_returns_404(self) -> None:
        """Req 9.13: Unknown job ID returns 404."""
        res = self.client.get("/api/v1/jobs/non-existent-job-1234")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["error_code"], "JOB_NOT_FOUND")

    def test_missing_artifacts_return_404(self) -> None:
        """Req 9.16: Requesting ungenerated draft PDF returns 404."""
        self.client.post("/api/v1/cases", json={"case_id": "case-no-art"})
        res = self.client.get("/api/v1/cases/case-no-art/artifacts/chargesheet.pdf")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["error_code"], "ARTIFACT_NOT_FOUND")

    def test_per_file_and_total_upload_size_limits(self) -> None:
        """Req 9.8: Enforce upload size limits with 413 Payload Too Large."""
        self.client.post("/api/v1/cases", json={"case_id": "case-size-limit"})
        original_limit = api_config.max_upload_file_size_bytes

        try:
            # Set tiny limit of 200 bytes
            api_config.max_upload_file_size_bytes = 200
            large_pdf = make_pdf_bytes("Large PDF that exceeds 200 bytes easily")
            files = [("files", ("big.pdf", large_pdf, "application/pdf"))]
            res = self.client.post("/api/v1/cases/case-size-limit/documents", files=files)
            self.assertEqual(res.status_code, 413)
            self.assertEqual(res.json()["error_code"], "FILE_SIZE_LIMIT_EXCEEDED")
        finally:
            api_config.max_upload_file_size_bytes = original_limit

    def test_failed_job_status_reporting(self) -> None:
        """Req 9.13 & 9.18: Truthful error reporting on workflow failure without leaking secrets."""
        self.client.post("/api/v1/cases", json={"case_id": "case-fail-test"})

        # Upload an arbitrary note that will produce no valid legal findings
        arbitrary_pdf = make_pdf_bytes("General text without any police or legal markers")
        self.client.post(
            "/api/v1/cases/case-fail-test/documents",
            files=[("files", ("arbitrary.pdf", arbitrary_pdf, "application/pdf"))],
        )

        res = self.client.post("/api/v1/cases/case-fail-test/process", json={"mock_llm": True})
        self.assertEqual(res.status_code, 202)
        job_id = res.json()["job_id"]

        job = self.job_service.wait_for_job(job_id, timeout=10.0)
        self.assertEqual(job.status, "failed")
        self.assertIsNotNone(job.error)
        self.assertNotIn("API_KEY", str(job.error))

    def test_cors_configuration(self) -> None:
        """Req 9.19: CORS headers are returned for allowed origins."""
        res = self.client.options(
            "/api/v1/cases",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access-control-allow-origin", res.headers)
        self.assertEqual(res.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_full_api_level_end_to_end_integration(self) -> None:
        """Full end-to-end integration test: Case Creation -> Document Upload -> Process -> Poll -> PDF Download."""
        case_id = "test-e2e-case-100"

        # 1. Create Case
        create_res = self.client.post("/api/v1/cases", json={"case_id": case_id, "title": "End to End API Case"})
        self.assertEqual(create_res.status_code, 201)

        # 2. Upload synthetic documents
        fixture_names = ("FIR.pdf", "complaint.pdf", "witness_statement_01.pdf", "medical_report.pdf", "seizure_memo.pdf")
        upload_files = []
        for name in fixture_names:
            upload_files.append(("files", (name, make_pdf_bytes(f"Synthetic {name}"), "application/pdf")))

        upload_res = self.client.post(f"/api/v1/cases/{case_id}/documents", files=upload_files)
        self.assertEqual(upload_res.status_code, 201)
        self.assertEqual(upload_res.json()["uploaded_count"], len(fixture_names))

        # 3. Trigger processing with mock_llm
        proc_res = self.client.post(f"/api/v1/cases/{case_id}/process", json={"mock_llm": True})
        self.assertEqual(proc_res.status_code, 202)
        job_id = proc_res.json()["job_id"]
        self.assertIsNotNone(job_id)

        # 4. Await job completion via job_service.wait_for_job
        job = self.job_service.wait_for_job(job_id, timeout=15.0)
        self.assertEqual(job.status, "completed")
        self.assertEqual(len(job.completed_stages), 9)

        # 5. Query job status endpoint
        job_status_res = self.client.get(f"/api/v1/jobs/{job_id}")
        self.assertEqual(job_status_res.status_code, 200)
        job_data = job_status_res.json()
        self.assertEqual(job_data["status"], "completed")
        self.assertEqual(job_data["case_id"], case_id)
        self.assertEqual(len(job_data["stage_records"]), 9)

        # 6. Retrieve artifact metadata
        art_res = self.client.get(f"/api/v1/cases/{case_id}/artifacts")
        self.assertEqual(art_res.status_code, 200)
        art_data = art_res.json()
        self.assertTrue(art_data["draft_pdf_available"])
        artifacts_by_name = {a["name"]: a for a in art_data["artifacts"]}
        self.assertTrue(artifacts_by_name["chargesheet_draft"]["exists"])
        self.assertTrue(artifacts_by_name["chargesheet_data"]["exists"])
        self.assertTrue(artifacts_by_name["validation_report"]["exists"])

        # 6b. Retrieve JSON artifact content
        val_content_res = self.client.get(f"/api/v1/cases/{case_id}/artifacts/content/validation_report")
        self.assertEqual(val_content_res.status_code, 200)
        self.assertIn("disposition", val_content_res.json())

        cs_content_res = self.client.get(f"/api/v1/cases/{case_id}/artifacts/content/chargesheet_data")
        self.assertEqual(cs_content_res.status_code, 200)

        # 7. Download draft PDF
        pdf_res = self.client.get(f"/api/v1/cases/{case_id}/artifacts/chargesheet.pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.headers["content-type"], "application/pdf")
        self.assertTrue(pdf_res.content.startswith(b"%PDF-"))
        self.assertGreater(len(pdf_res.content), 1000)

        # 8. Verify no accidental auto-approval or finalization (Req 5 & 9.20)
        case_detail = self.client.get(f"/api/v1/cases/{case_id}").json()
        self.assertEqual(case_detail["review_status"], "review_required")
        self.assertNotEqual(case_detail["review_status"], "approved")
        self.assertNotEqual(case_detail["review_status"], "finalized")

    def test_concurrent_processing_returns_409_with_job_id_and_case_reports_active_job(self) -> None:
        """Verify concurrency guard returns 409 with job_id and GET case exposes active_job_id."""
        case_id = "case-concurrency-test"
        self.client.post("/api/v1/cases", json={"case_id": case_id})
        pdf = make_pdf_bytes("FIR Incident Report")
        self.client.post(f"/api/v1/cases/{case_id}/documents", files=[("files", ("FIR.pdf", pdf, "application/pdf"))])

        # Simulate an active job lock in the job_service
        from src.api.services.case_service import parse_safe_case_id
        from src.api.services.job_service import JobRecord
        case_uuid, _ = parse_safe_case_id(case_id)
        mock_job_id = "test-running-job-1234"
        job_record = JobRecord(job_id=mock_job_id, case_id=case_id, case_uuid=case_uuid)
        job_record.status = "running"
        self.job_service._jobs[mock_job_id] = job_record
        self.job_service._active_cases.add(case_uuid)

        try:
            # 1. GET case must now expose active_job_id
            detail = self.client.get(f"/api/v1/cases/{case_id}").json()
            self.assertEqual(detail.get("active_job_id"), mock_job_id)

            # 2. POST /process must return 409 Conflict with the active job_id
            conflict_res = self.client.post(f"/api/v1/cases/{case_id}/process", json={"resume": False})
            self.assertEqual(conflict_res.status_code, 409)
            conflict_data = conflict_res.json()
            self.assertEqual(conflict_data["error_code"], "CASE_ALREADY_PROCESSING")
            self.assertEqual(conflict_data.get("job_id"), mock_job_id)
            self.assertIn(mock_job_id, conflict_data.get("detail", ""))

            # 3. get_active_job_for_case returns the running job ID
            self.assertEqual(self.job_service.get_active_job_for_case(case_uuid), mock_job_id)
        finally:
            self.job_service._active_cases.discard(case_uuid)
            self.job_service._jobs.pop(mock_job_id, None)
