"""Golden Case test for BYOMKESH_E2E_CASE_001 using the Legal Knowledge Graph."""

from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from uuid import uuid4

import pypdf

from src.extraction.ocr_client import OCRClient
from src.extraction.ocr_result import OCRMetadata, OCRPage, OCRResult
from src.intake.upload_manager import IncomingUpload
from src.legal.legal_findings import LegalFindingStatus
from src.legal.legal_rules import LocalLegalReferenceProvider
from src.parsers.base_parser import ParserClient
from src.review.review_service import ReviewService
from src.workflow.engine import WorkflowEngine
from src.workflow.production import create_production_registry, create_workflow_context
from src.workflow.state import StageStatus

CASE_DIR = Path(__file__).parents[1] / "BYOMKESH_E2E_CASE_001"
DATASET_PATH = Path(__file__).parents[1] / "references" / "legal" / "bns_sections.json"
DATASET_VERSION = "bns-2023-2024-07-01"


class PdfExtractingOCRClient(OCRClient):
    supported_mime_types = frozenset({"application/pdf"})

    def extract(self, document, source_path: Path) -> OCRResult:
        reader = pypdf.PdfReader(source_path)
        pages = []
        full_text = []
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            pages.append(OCRPage(page_number=i, text=text, confidence=0.95))
            full_text.append(text)
        joined = "\n".join(full_text)
        return OCRResult(
            document_id=document.id,
            pages=tuple(pages),
            raw_text=joined,
            confidence=0.95,
            metadata=OCRMetadata(provider="pypdf", model="extract", input_mime_type="application/pdf", processing_time_ms=5),
        )


class GoldenCaseParserClient(ParserClient):
    def generate_json(self, prompt: str) -> dict:
        if '"FIR"' in prompt:
            return {
                "fir_number": "47/2026",
                "registration_date": "2026-08-14",
                "police_station": "Shivaji Nagar Police Station",
                "complainant_name": "Neha Patil",
                "accused_names": ["Rohan Mehta"],
                "victim_names": ["Amit Kulkarni"],
                "vehicle_registrations": ["MH-12-AB-4821"],
                "occurrence_datetime": "2026-08-14T20:35:00",
                "occurrence_location": "Senapati Road junction, Pune",
                "jurisdiction": "Pune City",
                "court": "Sessions Court",
                "reported_sections": ["281"],
                "narrative_text": "Road traffic collision on public road. Vehicle struck pedestrian victim.",
                "confidence": 0.95,
            }
        if '"Complaint"' in prompt:
            return {
                "complaint_date": "2026-08-14",
                "complainant_name": "Neha Patil",
                "person_complained_against_names": ["Rohan Mehta"],
                "victim_names": ["Amit Kulkarni"],
                "vehicle_registrations": ["MH-12-AB-4821"],
                "complaint_text": "Accused was driving vehicle MH-12-AB-4821 and hit pedestrian.",
                "confidence": 0.95,
            }
        if '"MedicalReport"' in prompt:
            return {
                "report_number": "MLC-47/2026",
                "patient_name": "Amit Kulkarni",
                "doctor_name": "Dr. Joshi",
                "report_date": "2026-08-14",
                "observations": ["fracture of the left femur", "abrasions over right forearm", "contusion over left shoulder"],
                "confidence": 0.95,
            }
        if '"VehicleInspection"' in prompt:
            return {
                "report_number": "VI-47",
                "vehicle_registration": "MH-12-AB-4821",
                "inspection_date": "2026-08-15",
                "inspected_by": "Officer Kadam",
                "observations": ["damaged front portion", "dents on bumper"],
                "confidence": 0.95,
            }
        if '"SeizureMemo"' in prompt:
            return {
                "memo_number": "SZ-47",
                "seizure_datetime": "2026-08-14T21:00:00",
                "seizure_location": "Senapati Road junction, Pune",
                "seized_items": [{"description": "Vehicle MH-12-AB-4821", "exhibit_mark": "Ex-1"}],
                "confidence": 0.95,
            }
        if '"SitePlan"' in prompt:
            return {
                "plan_number": "SP-47",
                "location": "Senapati Road junction, Pune",
                "plan_date": "2026-08-14",
                "prepared_by": "Officer Kadam",
                "confidence": 0.95,
            }
        if '"FSLReport"' in prompt:
            return {
                "report_number": "FSL-47",
                "examined_items": ["swab/sample from damaged front portion"],
                "findings": ["sample matches victim blood group"],
                "confidence": 0.95,
            }
        if '"WitnessStatement"' in prompt:
            return {
                "witness_name": "Neha Patil",
                "statement_date": "2026-08-14",
                "statement_text": "I saw vehicle MH-12-AB-4821 hit the pedestrian at high speed on the road.",
                "confidence": 0.95,
            }
        return {"confidence": 0.9}


class GoldenCase001Tests(TestCase):
    def test_byomkesh_e2e_case_001_pipeline(self):
        with TemporaryDirectory() as directory:
            storage_root = Path(directory)
            uploads = tuple(
                IncomingUpload(source_path=f, original_filename=f.name)
                for f in sorted(CASE_DIR.glob("*.pdf"))
            )
            self.assertEqual(len(uploads), 9)

            context = create_workflow_context(uuid4(), uploads)
            registry = create_production_registry(
                storage_root,
                ocr_client=PdfExtractingOCRClient(),
                parser_client=GoldenCaseParserClient(),
                legal_reference_path=DATASET_PATH,
                legal_reference_version=DATASET_VERSION,
                allow_draft_legal=True,
            )

            result = WorkflowEngine(registry).run(context)
            self.assertTrue(result.report.successful)
            self.assertEqual(len(result.report.stage_records), 10)
            self.assertEqual(
                tuple(record.status for record in result.report.stage_records),
                (StageStatus.COMPLETED,) * 10,
            )

            # Check fact tagging results
            fact_tags_artifact = storage_root / f"CASE_{context.case_id.hex}" / "processed" / "legal" / "fact_tags.json"
            self.assertTrue(fact_tags_artifact.is_file())

            # Check legal findings
            findings = result.context.legal_findings
            self.assertIsNotNone(findings)
            self.assertTrue(len(findings.findings) > 0)

            # Check ChargeSheet Data & Draft PDF
            cs_data = result.context.chargesheet_data
            self.assertIsNotNone(cs_data)
            self.assertEqual(cs_data.police_station.value, "Shivaji Nagar Police Station")
            self.assertTrue(len(cs_data.legal_findings) > 0)

            artifacts = {item.name: storage_root / item.storage_key for item in result.context.generated_artifacts}
            self.assertIn("chargesheet_draft", artifacts)
            draft_pdf = artifacts["chargesheet_draft"]
            self.assertTrue(draft_pdf.is_file())
            self.assertGreater(draft_pdf.stat().st_size, 2000)

            # Verify officer review & approval
            review = result.context.officer_review
            approved = ReviewService().approve(review, cs_data, reviewer_id="inspector-deshmukh")
            finalized = ReviewService().finalize(approved, cs_data, storage_root=storage_root)
            final_pdf = storage_root / finalized.final_artifact_reference
            self.assertTrue(final_pdf.is_file())


if __name__ == "__main__":
    main()
