"""End-to-End Tests for Authentication, Dynamic Multi-Case Processing, and Strict Case Isolation."""

from __future__ import annotations

import io
import json
import re
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas

from src.api.app import create_app
from src.api.dependencies import (
    get_artifact_service,
    get_case_service,
    get_job_service,
    get_review_service,
    get_storage_root,
)
from src.api.services.artifact_service import ArtifactService
from src.api.services.case_review_service import CaseReviewService
from src.api.services.case_service import CaseService
from src.api.services.job_service import JobService


def create_test_pdf(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf)
    y = 780
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


class AuthAndDynamicCasesTests(TestCase):
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
        self.temp_dir.cleanup()

    def test_authentication_workflow(self) -> None:
        """Test login, /me token validation, invalid credentials, and logout."""
        # 1. Successful login
        res = self.client.post("/api/v1/auth/login", json={"badge_number": "inspector_sharma", "password": "investigator123"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("token", data)
        token = data["token"]
        self.assertEqual(data["officer"]["name"], "Inspector Ramesh Sharma")

        # 2. Authenticated user profile retrieval
        me_res = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.json()
        self.assertTrue(me_data["valid"])
        self.assertEqual(me_data["officer"]["badge_number"], "DL-RN-4501")

        # 3. Invalid credentials rejected
        bad_res = self.client.post("/api/v1/auth/login", json={"badge_number": "inspector_sharma", "password": "WrongPassword"})
        self.assertEqual(bad_res.status_code, 401)

        # 4. Logout invalidates session
        logout_res = self.client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_res.status_code, 200)

        # 5. Subsequent access is unauthorized
        me_after_logout = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_after_logout.status_code, 401)

    def test_multi_case_isolation_and_dynamic_extraction(self) -> None:
        """Process two completely distinct cases and verify zero cross-contamination."""
        case_a_id = "delhi_collision_case"
        case_b_id = "bangalore_theft_case"

        self.client.post("/api/v1/cases", json={"case_id": case_a_id, "title": "Delhi Collision"})
        self.client.post("/api/v1/cases", json={"case_id": case_b_id, "title": "Bangalore Incident"})

        # Case A Documents: Delhi Traffic Collision
        doc_a_fir = create_test_pdf([
            "FIRST INFORMATION REPORT (Under Section 173 BNSS)",
            "State: Delhi District: Central Delhi Police Station: Rajinder Nagar Police Station",
            "FIR No: FIR/2024/DL/PSRKP/0452 Date Of Fir: 2024-10-15",
            "Complainant: Sunita Sharma",
            "ACCUSED DETAILS Name: Amit Verma",
            "VICTIM DETAILS Name: Rajesh Kumar Sharma",
            "Vehicles: DL2SBP1234 and DL5SCT5678",
            "Place Of Occurrence: Shankar Road T-Point",
            "Brief Facts: High speed collision at Shankar Road T-Point.",
            "Sections: Section 281, Section 125 BNS",
        ])
        doc_a_med = create_test_pdf([
            "MEDICO-LEGAL EXAMINATION REPORT (MLC)",
            "MLC No: MLC-PSRKP-0452 Date: 2024-10-15",
            "Hospital: St. Stephen's Hospital, Tis Hazari, Delhi",
            "Patient Name: Rajesh Kumar Sharma",
            "Injuries: Compound fracture femur, clavicle fracture.",
            "Nature of injury: Grievous hurt. Patient is alive and admitted.",
        ])
        doc_a_pm = create_test_pdf([
            "POST-MORTEM STATUS REPORT",
            "Status: Not Applicable",
            "Victim Rajesh Kumar Sharma is alive and undergoing medical treatment.",
        ])

        # Case B Documents: Bangalore Incident
        doc_b_fir = create_test_pdf([
            "FIRST INFORMATION REPORT (Under Section 173 BNSS)",
            "State: Karnataka District: Bengaluru Police Station: Indiranagar Police Station",
            "FIR No: FIR/2025/KA/BLR/0987 Date Of Fir: 2025-03-20",
            "Complainant: Pooja Hegde",
            "ACCUSED DETAILS Name: Vikram Malhotra",
            "VICTIM DETAILS Name: Karthik Gowda",
            "Vehicles: KA03MN9999 and KA04XY1111",
            "Place Of Occurrence: 100 Feet Road, Indiranagar",
            "Brief Facts: Robbery and vehicular collision at 100 Feet Road.",
            "Sections: Section 309, Section 281 BNS",
        ])
        doc_b_med = create_test_pdf([
            "MEDICO-LEGAL EXAMINATION REPORT (MLC)",
            "MLC No: MLC-BLR-0987 Date: 2025-03-20",
            "Hospital: Manipal Hospital, Bengaluru",
            "Patient Name: Karthik Gowda",
            "Injuries: Contusion over shoulder, blunt injury.",
            "Nature of injury: Bodily hurt. Patient alive and discharged.",
        ])

        # Upload Case A documents
        files_a = [
            ("files", ("fir_delhi.pdf", doc_a_fir, "application/pdf")),
            ("files", ("mlc_delhi.pdf", doc_a_med, "application/pdf")),
            ("files", ("pm_delhi.pdf", doc_a_pm, "application/pdf")),
        ]
        u_res_a = self.client.post(f"/api/v1/cases/{case_a_id}/documents", files=files_a)
        self.assertEqual(u_res_a.status_code, 201)

        # Upload Case B documents
        files_b = [
            ("files", ("fir_blr.pdf", doc_b_fir, "application/pdf")),
            ("files", ("mlc_blr.pdf", doc_b_med, "application/pdf")),
        ]
        u_res_b = self.client.post(f"/api/v1/cases/{case_b_id}/documents", files=files_b)
        self.assertEqual(u_res_b.status_code, 201)

        # Process Case A
        p_res_a = self.client.post(f"/api/v1/cases/{case_a_id}/process", json={"mock_llm": True})
        self.assertEqual(p_res_a.status_code, 202)
        job_a = self.job_service.wait_for_job(p_res_a.json()["job_id"], timeout=20.0)
        self.assertEqual(job_a.status, "completed")

        # Process Case B
        p_res_b = self.client.post(f"/api/v1/cases/{case_b_id}/process", json={"mock_llm": True})
        self.assertEqual(p_res_b.status_code, 202)
        job_b = self.job_service.wait_for_job(p_res_b.json()["job_id"], timeout=20.0)
        self.assertEqual(job_b.status, "completed")

        # 1. VERIFY CASE A CHARGE SHEET DATA
        rev_a = self.client.get(f"/api/v1/cases/{case_a_id}/review").json()["charge_sheet_data"]
        self.assertIn("0452", rev_a["case_number"]["value"])
        self.assertIn("Rajinder Nagar", rev_a["police_station"]["value"])
        acc_a = [x["description"]["value"] for x in rev_a.get("accused", [])]
        self.assertTrue(any("Amit Verma" in a for a in acc_a))
        self.assertFalse(any("Vikram Malhotra" in a for a in acc_a))
        vic_a = [x["description"]["value"] for x in rev_a.get("victims", [])]
        self.assertTrue(any("Rajesh Kumar Sharma" in v for v in vic_a))
        self.assertFalse(any("Karthik Gowda" in v for v in vic_a))

        # 2. VERIFY CASE B CHARGE SHEET DATA
        rev_b = self.client.get(f"/api/v1/cases/{case_b_id}/review").json()["charge_sheet_data"]
        self.assertIn("0987", rev_b["case_number"]["value"])
        self.assertIn("Indiranagar", rev_b["police_station"]["value"])
        acc_b = [x["description"]["value"] for x in rev_b.get("accused", [])]
        self.assertTrue(any("Vikram Malhotra" in a for a in acc_b))
        self.assertFalse(any("Amit Verma" in a for a in acc_b))
        vic_b = [x["description"]["value"] for x in rev_b.get("victims", [])]
        self.assertTrue(any("Karthik Gowda" in v for v in vic_b))
        self.assertFalse(any("Rajesh Kumar Sharma" in v for v in vic_b))

        # 3. VERIFY RAG RETRIEVAL ISOLATION
        rag_a = self.client.get(f"/api/v1/cases/{case_a_id}/review/retrieval?query=Amit&top_k=5").json()
        for p in rag_a["passages"]:
            self.assertNotIn("Vikram Malhotra", p["text"])
            self.assertNotIn("Indiranagar", p["text"])

        rag_b = self.client.get(f"/api/v1/cases/{case_b_id}/review/retrieval?query=Vikram&top_k=5").json()
        for p in rag_b["passages"]:
            self.assertNotIn("Amit Verma", p["text"])
            self.assertNotIn("Rajinder Nagar", p["text"])

        # 4. VERIFY PDF ARTIFACT ISOLATION
        pdf_res_a = self.client.get(f"/api/v1/cases/{case_a_id}/artifacts/chargesheet.pdf")
        self.assertEqual(pdf_res_a.status_code, 200)
        self.assertTrue(pdf_res_a.content.startswith(b"%PDF-"))

        pdf_res_b = self.client.get(f"/api/v1/cases/{case_b_id}/artifacts/chargesheet.pdf")
        self.assertEqual(pdf_res_b.status_code, 200)
        self.assertTrue(pdf_res_b.content.startswith(b"%PDF-"))
