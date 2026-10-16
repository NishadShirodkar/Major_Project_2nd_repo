"""Regression tests for Phase 1: Backend Stabilization."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import uuid4

from reportlab.pdfgen.canvas import Canvas

from src.chargesheet.chargesheet_stage import ChargeSheetStage
from src.context.case_context_builder import CaseContextBuilder
from src.context.context_stage import CaseContextStage
from src.domain.documents import (
    ClassificationStatus,
    ConfidenceLevel,
    DocumentType,
    ExtractionState,
    ParsingState,
    ProcessingCapability,
    SourceDocument,
)
from src.domain.parsed_documents import FIR, UnknownDocument
from src.normalization.canonical_stage import CanonicalInvestigationStage
from src.extraction.mock_client import MockOCRClient, MockParserClient
from src.extraction.ocr_client import OCRClient
from src.extraction.ocr_result import OCRMetadata, OCRPage, OCRResult
from src.extraction.ocr_stage import OCRStage
from src.intake.document_classifier import DeterministicDocumentClassifier
from src.intake.document_intake_stage import DocumentIntakeStage
from src.intake.upload_manager import IncomingUpload
from src.knowledge_graph.graph_stage import GraphStage
from src.legal.legal_stage import LegalReasoningStage
from src.legal.legal_rules import LocalLegalReferenceProvider
from src.main import main as cli_main
from src.parsers.base_parser import BaseDocumentParser, ParserClient, ParserError
from src.parsers.parser_registry import ParserRegistry, create_default_parser_registry
from src.parsers.parser_stage import ParserStage
from src.validation.evidence_validator import EvidenceValidator
from src.validation.validation_models import ValidationDisposition, ValidationRules
from src.validation.validation_stage import EvidenceValidationStage
from src.workflow.context import ContextItem, WorkflowContext
from src.workflow.engine import WorkflowEngine
from src.workflow.production import STAGE_ORDER, create_production_registry, create_workflow_context
from src.workflow.registry import StageRegistry
from src.workflow.state import StageStatus, WorkflowState


LEGAL_REF_PATH = Path(__file__).parents[1] / "references" / "legal" / "bns_sections.json"
LEGAL_REF_VERSION = "bns-2023-2024-07-01"


class SelectiveFailingOCR(OCRClient):
    supported_mime_types = frozenset({"application/pdf"})

    def __init__(self, failing_filename: str):
        self.failing_filename = failing_filename

    def extract(self, document: SourceDocument, source_path: Path) -> OCRResult:
        if document.original_filename == self.failing_filename:
            raise RuntimeError(f"Simulated OCR extraction hardware failure on {document.original_filename}")
        text = f"Sample OCR text for {document.original_filename}"
        return OCRResult(
            document_id=document.id,
            pages=(OCRPage(page_number=1, text=text, confidence=0.9),),
            raw_text=text,
            confidence=0.9,
            metadata=OCRMetadata(
                provider="mock",
                model="test",
                input_mime_type="application/pdf",
                processing_time_ms=1.0,
            ),
        )


class SelectiveFailingParser(ParserClient):
    def __init__(self, failing_type: str):
        self.failing_type = failing_type

    def generate_json(self, prompt: str):
        if self.failing_type in prompt:
            raise ParserError(f"Simulated parsing schema failure for {self.failing_type}")
        if '"FIR"' in prompt:
            return {
                "fir_number": "42/2026",
                "police_station": "Central PS",
                "complainant_name": "Asha Devi",
                "reported_sections": ["115"],
                "confidence": 0.9,
            }
        return {"confidence": 0.9}


class Phase1StabilityTests(TestCase):
    def test_single_document_ocr_failure_does_not_halt_unrelated_documents(self):
        """Req 3B: A single document's failure does not terminate processing of other documents."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage = root / "storage"
            case_id = uuid4()

            p1 = root / "doc_good_1.pdf"
            p2 = root / "doc_bad.pdf"
            p3 = root / "doc_good_2.pdf"
            for p in (p1, p2, p3):
                Canvas(str(p)).save()

            uploads = (
                IncomingUpload(source_path=p1, original_filename="doc_good_1.pdf"),
                IncomingUpload(source_path=p2, original_filename="doc_bad.pdf"),
                IncomingUpload(source_path=p3, original_filename="doc_good_2.pdf"),
            )
            context = create_workflow_context(case_id, uploads)

            engine = WorkflowEngine(StageRegistry((
                DocumentIntakeStage(storage),
                OCRStage(storage, SelectiveFailingOCR(failing_filename="doc_bad.pdf")),
            )))
            result = engine.run(context)

            self.assertTrue(result.report.successful)
            ocr_record = result.context.execution_state.record_for("ocr")
            self.assertEqual(ocr_record.status, StageStatus.COMPLETED)

            docs = {doc.original_filename: doc for doc in result.context.uploaded_documents}
            self.assertEqual(docs["doc_good_1.pdf"].extraction_state, ExtractionState.COMPLETE)
            self.assertEqual(docs["doc_bad.pdf"].extraction_state, ExtractionState.FAILED)
            self.assertEqual(docs["doc_good_2.pdf"].extraction_state, ExtractionState.COMPLETE)
            self.assertEqual(len(result.context.ocr_results), 2)

    def test_case_level_critical_ocr_failure_stops_when_all_fail(self):
        """Req 3B: Pipeline stops when a critical condition makes further processing unsafe."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage = root / "storage"
            case_id = uuid4()

            p = root / "failing.pdf"
            Canvas(str(p)).save()

            uploads = (IncomingUpload(source_path=p, original_filename="failing.pdf"),)
            context = create_workflow_context(case_id, uploads)

            engine = WorkflowEngine(StageRegistry((
                DocumentIntakeStage(storage),
                OCRStage(storage, SelectiveFailingOCR(failing_filename="failing.pdf")),
            )))
            result = engine.run(context)

            self.assertFalse(result.report.successful)
            ocr_record = result.context.execution_state.record_for("ocr")
            self.assertEqual(ocr_record.status, StageStatus.FAILED)

    def test_single_document_parser_failure_isolated_from_other_documents(self):
        """Req 3B: Parser failure on one document does not crash other documents."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage = root / "storage"
            case_id = uuid4()
            now = datetime.now(timezone.utc)

            doc_fir = SourceDocument(
                case_id=case_id,
                original_filename="fir.pdf",
                storage_key="fir.pdf",
                media_type="application/pdf",
                sha256="a" * 64,
                size_bytes=100,
                detected_type=DocumentType.FIR,
                extraction_state=ExtractionState.COMPLETE,
                processing_capability=ProcessingCapability.OCR_SUPPORTED,
                parsing_state=ParsingState.PENDING,
                uploaded_at=now,
            )
            doc_comp = SourceDocument(
                case_id=case_id,
                original_filename="complaint.pdf",
                storage_key="complaint.pdf",
                media_type="application/pdf",
                sha256="b" * 64,
                size_bytes=100,
                detected_type=DocumentType.COMPLAINT,
                extraction_state=ExtractionState.COMPLETE,
                processing_capability=ProcessingCapability.OCR_SUPPORTED,
                parsing_state=ParsingState.PENDING,
                uploaded_at=now,
            )

            ocr_fir = OCRResult(
                document_id=doc_fir.id,
                pages=(OCRPage(page_number=1, text="FIR text", confidence=0.9),),
                raw_text="FIR 42/2026 Central PS Complainant: Asha Devi Reported Section: 115",
                confidence=0.9,
                metadata=OCRMetadata(provider="test", model="test", input_mime_type="application/pdf", processing_time_ms=1.0),
            )
            ocr_comp = OCRResult(
                document_id=doc_comp.id,
                pages=(OCRPage(page_number=1, text="Complaint text", confidence=0.9),),
                raw_text="Complaint text",
                confidence=0.9,
                metadata=OCRMetadata(provider="test", model="test", input_mime_type="application/pdf", processing_time_ms=1.0),
            )

            client = SelectiveFailingParser(failing_type="Complaint")
            registry = create_default_parser_registry(client)

            context = WorkflowContext(
                case_id=case_id,
                uploaded_documents=(doc_fir, doc_comp),
                ocr_results=(
                    ContextItem(key=str(doc_fir.id), value=ocr_fir),
                    ContextItem(key=str(doc_comp.id), value=ocr_comp),
                ),
                execution_state=WorkflowState(case_id=case_id),
            )

            stage = ParserStage(storage, registry)
            engine = WorkflowEngine(StageRegistry((stage,)))
            result = engine.run(context)

            self.assertTrue(result.report.successful)
            record = result.context.execution_state.record_for("document_parsing")
            self.assertEqual(record.status, StageStatus.COMPLETED)

            docs = {doc.original_filename: doc for doc in result.context.uploaded_documents}
            self.assertEqual(docs["fir.pdf"].parsing_state, ParsingState.COMPLETE)
            self.assertEqual(docs["complaint.pdf"].parsing_state, ParsingState.FAILED)
            self.assertEqual(len(result.context.parsed_documents), 1)

    def test_generic_filename_content_classification_and_safe_fallback(self):
        """Req 3C: Generic filenames e.g. scan_001.pdf are classified by content or fall back safely."""
        classifier = DeterministicDocumentClassifier()

        fir_content = "FIRST INFORMATION REPORT Under Section 154 CrPC FIR No: 12/2026"
        res_fir = classifier.classify("scan_001.pdf", "application/pdf", content=fir_content)
        self.assertEqual(res_fir.document_type, DocumentType.FIR)
        self.assertEqual(res_fir.confidence, ConfidenceLevel.HIGH)

        unknown_content = "Generic meeting notes from office discussion with no police markers."
        res_unknown = classifier.classify("scan_002.pdf", "application/pdf", content=unknown_content)
        self.assertEqual(res_unknown.document_type, DocumentType.OTHER)
        self.assertEqual(res_unknown.confidence, ConfidenceLevel.LOW)

    def test_unknown_document_parsed_safely_without_crashing_pipeline(self):
        """Req 3C: Unknown document types do not crash the pipeline."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage = root / "storage"
            case_id = uuid4()

            doc_other = SourceDocument(
                case_id=case_id,
                original_filename="random_note.pdf",
                storage_key="random_note.pdf",
                media_type="application/pdf",
                sha256="c" * 64,
                size_bytes=100,
                detected_type=DocumentType.OTHER,
                extraction_state=ExtractionState.COMPLETE,
                processing_capability=ProcessingCapability.OCR_SUPPORTED,
                parsing_state=ParsingState.PENDING,
                uploaded_at=root.stat().st_ctime,
            )
            ocr_other = OCRResult(
                document_id=doc_other.id,
                pages=(OCRPage(page_number=1, text="Arbitrary notes without case markers", confidence=0.8),),
                raw_text="Arbitrary notes without case markers",
                confidence=0.8,
                metadata=OCRMetadata(provider="test", model="test", input_mime_type="application/pdf", processing_time_ms=1.0),
            )

            registry = create_default_parser_registry(MockParserClient())
            context = WorkflowContext(
                case_id=case_id,
                uploaded_documents=(doc_other,),
                ocr_results=(ContextItem(key=str(doc_other.id), value=ocr_other),),
                execution_state=WorkflowState(case_id=case_id),
            )

            engine = WorkflowEngine(StageRegistry((
                ParserStage(storage, registry),
                GraphStage(storage),
            )))
            result = engine.run(context)

            self.assertTrue(result.report.successful)
            self.assertEqual(result.context.uploaded_documents[0].parsing_state, ParsingState.COMPLETE)
            self.assertIsInstance(result.context.parsed_documents[0].value, UnknownDocument)
            self.assertIsNotNone(result.context.investigation_knowledge_graph)

    def test_nine_stages_execute_in_correct_order(self):
        """Req 3A: Production workflow invokes the 9 stages in the exact required order."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage = root / "storage"
            registry = create_production_registry(
                storage,
                ocr_client=MockOCRClient(),
                parser_client=MockParserClient(),
                legal_reference_path=LEGAL_REF_PATH,
                legal_reference_version=LEGAL_REF_VERSION,
            )
            self.assertEqual(tuple(stage.name for stage in registry.stages), STAGE_ORDER)
            self.assertEqual(len(STAGE_ORDER), 9)

    def test_case_outputs_remain_isolated_across_different_cases(self):
        """Req 3E: Processing one case cannot mix documents or artifacts from another case."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage = root / "storage"
            case_1 = uuid4()
            case_2 = uuid4()

            p1_fir = root / "c1_fir.pdf"
            p1_med = root / "c1_medical.pdf"
            p2_fir = root / "c2_fir.pdf"
            p2_med = root / "c2_medical.pdf"
            for p in (p1_fir, p1_med, p2_fir, p2_med):
                Canvas(str(p)).save()

            ctx1 = create_workflow_context(
                case_1,
                (
                    IncomingUpload(source_path=p1_fir, original_filename="FIR.pdf"),
                    IncomingUpload(source_path=p1_med, original_filename="medical.pdf"),
                ),
            )
            ctx2 = create_workflow_context(
                case_2,
                (
                    IncomingUpload(source_path=p2_fir, original_filename="FIR.pdf"),
                    IncomingUpload(source_path=p2_med, original_filename="medical.pdf"),
                ),
            )

            reg1 = create_production_registry(
                storage,
                ocr_client=MockOCRClient(),
                parser_client=MockParserClient(),
                legal_reference_path=LEGAL_REF_PATH,
                legal_reference_version=LEGAL_REF_VERSION,
            )
            reg2 = create_production_registry(
                storage,
                ocr_client=MockOCRClient(),
                parser_client=MockParserClient(),
                legal_reference_path=LEGAL_REF_PATH,
                legal_reference_version=LEGAL_REF_VERSION,
            )

            res1 = WorkflowEngine(reg1).run(ctx1)
            res2 = WorkflowEngine(reg2).run(ctx2)

            self.assertTrue(res1.report.successful)
            self.assertTrue(res2.report.successful)
            self.assertNotEqual(res1.context.case_id, res2.context.case_id)

            dir1 = storage / f"CASE_{res1.context.case_id.hex}"
            dir2 = storage / f"CASE_{res2.context.case_id.hex}"
            self.assertTrue(dir1.is_dir())
            self.assertTrue(dir2.is_dir())
            self.assertNotEqual(dir1, dir2)

    def test_missing_gemini_api_key_produces_clear_actionable_error(self):
        """Req 3F: Missing API keys should produce clear, actionable errors."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            (input_dir / "sample.pdf").write_bytes(b"%PDF-1.4 sample")

            ret = cli_main([
                "--case-id", "test-case-missing-key",
                "--input-dir", str(input_dir),
                "--output-dir", str(output_dir),
                "--gemini-api-key", "",
            ])
            self.assertEqual(ret, 2)

    def test_cli_end_to_end_with_mock_llm_succeeds(self):
        """Req 4 & 5: Synthetic end-to-end workflow produces draft artifacts without Gemini keys."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()

            for name in ("FIR.pdf", "complaint.pdf", "witness.pdf", "medical.pdf", "seizure.pdf"):
                p = input_dir / name
                Canvas(str(p)).save()

            ret = cli_main([
                "--case-id", "test-synthetic-case",
                "--input-dir", str(input_dir),
                "--output-dir", str(output_dir),
                "--mock-llm",
                "--legal-reference-path", str(LEGAL_REF_PATH),
                "--legal-reference-version", LEGAL_REF_VERSION,
            ])
            self.assertEqual(ret, 0)

            # Verify draft artifacts
            case_dirs = list(output_dir.glob("CASE_*"))
            self.assertEqual(len(case_dirs), 1)
            case_dir = case_dirs[0]

            processed_dir = case_dir / "processed"
            self.assertTrue((processed_dir / "upload_manifest.json").is_file())
            self.assertTrue((processed_dir / "context" / "case_context.json").is_file())
            self.assertTrue((processed_dir / "chargesheet" / "draft" / "ChargeSheet_v1_data.json").is_file())
            self.assertTrue((processed_dir / "chargesheet" / "draft" / "ChargeSheet_v1_review.pdf").is_file())
            self.assertTrue((processed_dir / "chargesheet" / "review_state.json").is_file())

            # Verify case context occurrence details are populated
            case_ctx = json.loads((processed_dir / "context" / "case_context.json").read_text())
            self.assertGreater(len(case_ctx["occurrence_details"]), 0)
