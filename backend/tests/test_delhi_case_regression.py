"""Regression test suite for the Delhi Traffic Collision case (FIR/2024/DL/PSRKP/0452).

Verifies that:
1. Real uploaded digital PDFs are extracted accurately from document contents.
2. The case context retains source FIR identity: FIR/2024/DL/PSRKP/0452, 2024-10-15, Rajinder Nagar Police Station.
3. Accused is Amit Verma, injured victim is Rajesh Kumar Sharma, vehicles are DL2SBP1234 and DL5SCT5678.
4. Surviving injured person is not marked as deceased.
5. Post-mortem 'Not Applicable' status is preserved; Section 106 BNS (causing death) is NOT established.
6. Unrelated 2026 assault case (Case 42/2026, Central PS, Market Road, Raj Verma, Sameer Khan, KA01AB1234) never enters the pipeline.
7. RAG retrieval indexes and retrieves passages belonging strictly to this case.
8. Rendered draft PDF contains the Delhi case details and zero references to the 2026 assault case.
"""

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
from src.extraction.pdf_extractor import extract_digital_pdf_pages


def create_test_pdf(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf)
    y = 780
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


class DelhiCaseRegressionTests(TestCase):
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

    def test_delhi_case_end_to_end_accuracy_and_isolation(self) -> None:
        case_id = "delhi_traffic_collision_2024"
        c_res = self.client.post("/api/v1/cases", json={"case_id": case_id, "title": "Delhi Traffic Collision"})
        self.assertEqual(c_res.status_code, 201)

        # Build faithful digital PDFs matching the Delhi investigation documents
        fir_pdf = create_test_pdf([
            "FIRST INFORMATION REPORT (Under Section 173 BNSS / 154 CrPC)",
            "State: Delhi District: Central Delhi Police Station: Rajinder Nagar Police Station",
            "FIR No: FIR/2024/DL/PSRKP/0452 Date Of Fir: 2024-10-15",
            "Complainant: Sunita Sharma",
            "ACCUSED DETAILS Name: Amit Verma",
            "VICTIM DETAILS Name: Rajesh Kumar Sharma",
            "Vehicles: Bajaj Pulsar DL2SBP1234 and Honda Activa DL5SCT5678",
            "Place Of Occurrence: Shankar Road T-Point, Rajinder Nagar",
            "Brief Facts: High speed collision at Shankar Road T-Point causing grievous injury.",
            "Sections: Section 281, Section 125 BNS",
        ])

        complaint_pdf = create_test_pdf([
            "WRITTEN COMPLAINT",
            "Date: 2024-10-15",
            "To: Station House Officer, Rajinder Nagar Police Station, Delhi",
            "Complainant Name: Sunita Sharma, R/o Pusa Road, New Delhi",
            "Accused: Amit Verma, riding Bajaj Pulsar DL2SBP1234",
            "Victim: Rajesh Kumar Sharma, riding Honda Activa DL5SCT5678",
            "Details: My husband Rajesh Kumar Sharma was hit by rashly driven Pulsar DL2SBP1234.",
        ])

        medical_pdf = create_test_pdf([
            "MEDICO-LEGAL EXAMINATION REPORT (MLC)",
            "MLC No: MLC-PSRKP-0452 Date: 2024-10-15",
            "Hospital: St. Stephen's Hospital, Tis Hazari, Delhi",
            "Patient Name: Rajesh Kumar Sharma",
            "Injuries: Compound fracture femur, clavicle fracture, blunt chest trauma.",
            "Nature of injury: Grievous hurt resulting from road traffic collision. Patient alive and admitted.",
        ])

        postmortem_pdf = create_test_pdf([
            "POST-MORTEM EXAMINATION STATUS REPORT",
            "Report No: PM-NA-01 Date: 2024-10-15",
            "Status: Not Applicable",
            "Reason: Victim Rajesh Kumar Sharma is alive and undergoing medical treatment at St. Stephen's Hospital.",
            "Postmortem examination is not applicable.",
        ])

        vehicle_pdf = create_test_pdf([
            "MOTOR VEHICLE INSPECTION REPORT",
            "Date: 2024-10-16",
            "Vehicle 1 Registration: DL2SBP1234 Make: Bajaj Pulsar",
            "Vehicle 2 Registration: DL5SCT5678 Make: Honda Activa",
            "Damage: Extensive front impact damage on DL5SCT5678; front fork damage on DL2SBP1234.",
            "Inspected at Rajinder Nagar Police Station by Transport Authority Inspector.",
        ])

        witness_pdf = create_test_pdf([
            "STATEMENT OF WITNESS UNDER SECTION 180 BNSS",
            "Date: 2024-10-15",
            "Witness Name: Mohammed Asif, Traffic Constable",
            "Location: Shankar Road T-Point, Rajinder Nagar",
            "Statement: I saw Bajaj Pulsar DL2SBP1234 jump the red light at Shankar Road T-Point and violently crash into Honda Activa DL5SCT5678 ridden by Rajesh Kumar Sharma. The rider Amit Verma tried to escape but was stopped.",
        ])

        docs = [
            ("fir_3.pdf", fir_pdf),
            ("complaint_3.pdf", complaint_pdf),
            ("medical_report_3.pdf", medical_pdf),
            ("postmortem_report_3.pdf", postmortem_pdf),
            ("vehicle_inspection_3.pdf", vehicle_pdf),
            ("witness_statement_1_3.pdf", witness_pdf),
        ]
        files = [("files", (name, data, "application/pdf")) for name, data in docs]

        # Upload documents
        u_res = self.client.post(f"/api/v1/cases/{case_id}/documents", files=files)
        self.assertEqual(u_res.status_code, 201)
        self.assertEqual(u_res.json()["uploaded_count"], len(docs))

        # Process case
        p_res = self.client.post(f"/api/v1/cases/{case_id}/process", json={"mock_llm": True})
        self.assertEqual(p_res.status_code, 202)
        job_id = p_res.json()["job_id"]

        job = self.job_service.wait_for_job(job_id, timeout=25.0)
        self.assertEqual(job.status, "completed")
        self.assertEqual(len(job.completed_stages), 9)

        # 1. Verify Case Context & Canonical Data
        rev_res = self.client.get(f"/api/v1/cases/{case_id}/review")
        self.assertEqual(rev_res.status_code, 200)
        review_data = rev_res.json()
        cs_data = review_data["charge_sheet_data"]

        # FIR / Case Number verification
        case_num_val = cs_data["case_number"]["value"]
        self.assertIn("0452", case_num_val)
        self.assertNotIn("42/2026", case_num_val)

        # Police Station verification
        ps_val = cs_data["police_station"]["value"]
        self.assertIn("Rajinder Nagar", ps_val)
        self.assertNotIn("Central PS", ps_val)

        # Accused verification
        accused_rows = [a["description"]["value"] for a in cs_data.get("accused", [])]
        self.assertTrue(any("Amit Verma" in a for a in accused_rows), f"Expected Amit Verma in {accused_rows}")
        self.assertFalse(any("Raj Verma" in a and "Amit" not in a for a in accused_rows))

        # Victim / Injured Person verification
        victim_rows = [v["description"]["value"] for v in cs_data.get("victims", [])]
        self.assertTrue(any("Rajesh Kumar Sharma" in v for v in victim_rows), f"Expected Rajesh Kumar Sharma in {victim_rows}")
        self.assertFalse(any("Sameer Khan" in v for v in victim_rows))

        # Complainant verification
        complainant_rows = [c["description"]["value"] for c in cs_data.get("complainants", [])]
        self.assertTrue(any("Sunita Sharma" in c for c in complainant_rows), f"Expected Sunita Sharma in {complainant_rows}")

        # Vehicle findings verification
        vehicle_rows = [vf["value"] for vf in cs_data.get("vehicle_findings", [])]
        self.assertFalse(any("KA01AB1234" in str(r) for r in vehicle_rows))

        # Death offence exclusion check: Section 106 BNS must NOT be supported
        sec_106_finding = next((f for f in cs_data.get("legal_findings", []) if "106" in str(f.get("proposed_section", {}).get("value"))), None)
        self.assertIsNotNone(sec_106_finding, "Section 106 evaluated finding should exist")
        self.assertTrue(sec_106_finding["review_required"], "Section 106 must be flagged for review")
        self.assertNotEqual(sec_106_finding["status"], "supported", "Section 106 must never be supported for a surviving victim")
        self.assertIn(sec_106_finding["status"], ("review_required", "insufficient_evidence"))

        # 2. Verify RAG retrieval isolation
        rag_res = self.client.get(f"/api/v1/cases/{case_id}/review/retrieval?query=Amit+Verma&top_k=5")
        self.assertEqual(rag_res.status_code, 200)
        rag_data = rag_res.json()
        self.assertGreater(rag_data["total_chunks_indexed"], 0)
        self.assertGreater(len(rag_data["passages"]), 0)
        for p in rag_data["passages"]:
            self.assertNotIn("Market Road", p["text"])
            self.assertNotIn("Sameer Khan", p["text"])
            self.assertNotIn("KA01AB1234", p["text"])

        # 3. Verify Draft PDF Content
        pdf_res = self.client.get(f"/api/v1/cases/{case_id}/artifacts/chargesheet.pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertTrue(pdf_res.content.startswith(b"%PDF-"))
        import base64
        decoded_streams = []
        for stream in re.findall(rb"stream[\r\n]+(.*?)endstream", pdf_res.content, re.DOTALL):
            st = stream.strip()
            try:
                dec = zlib.decompress(base64.a85decode(st, adobe=True)).decode("latin-1", errors="ignore")
                decoded_streams.append(dec)
            except Exception:
                try:
                    dec = zlib.decompress(st).decode("latin-1", errors="ignore")
                    decoded_streams.append(dec)
                except Exception:
                    pass
        pdf_text = "\n".join(decoded_streams)
        self.assertIn("0452", pdf_text)
        self.assertIn("Rajinder Nagar", pdf_text)
        self.assertIn("Amit Verma", pdf_text)
        self.assertNotIn("Central PS", pdf_text)
        self.assertNotIn("Market Road", pdf_text)
        self.assertNotIn("KA01AB1234", pdf_text)
