"""Comprehensive tests for case-isolated RAG integration, chunking, and legal reasoning."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from src.context.case_context import CaseContext
from src.domain.common import ConfidenceLevel, SourceLocation, SourceReference
from src.domain.documents import DocumentType, ExtractionState, SourceDocument, ValidationStatus
from src.extraction.ocr_result import OCRMetadata, OCRPage, OCRResult
from src.legal.legal_findings import IngredientStatus, LegalFindingStatus
from src.legal.legal_reasoner import LegalReasoner
from src.legal.legal_rules import LocalLegalReferenceProvider
from src.rag.case_retriever import CaseIsolationViolationError, CaseRetriever
from src.rag.document_chunker import DocumentChunker
from src.rag.embedding_provider import MockEmbeddingProvider, NoOpEmbeddingProvider
from src.rag.rag_models import DocumentChunk, RelevanceCategory
from src.rendering.if5_renderer import IF5Renderer
from src.chargesheet.chargesheet_populator import ChargeSheetPopulator


def _make_source_doc(case_id, name="witness_statement.txt") -> SourceDocument:
    doc_id = uuid4()
    return SourceDocument(
        id=doc_id,
        case_id=case_id,
        original_filename=name,
        storage_key=f"CASE_{case_id.hex}/originals/{doc_id}.txt",
        media_type="text/plain",
        sha256="a" * 64,
        size_bytes=1024,
        declared_type=DocumentType.WITNESS_STATEMENT,
        detected_type=DocumentType.WITNESS_STATEMENT,
        validation_status=ValidationStatus.VALID,
        extraction_state=ExtractionState.COMPLETE,
        uploaded_at="2026-10-15T10:00:00Z",
    )


def _make_ocr_result(doc_id, pages_text: list[str]) -> OCRResult:
    pages = tuple(
        OCRPage(page_number=i + 1, text=txt, confidence=0.92)
        for i, txt in enumerate(pages_text)
    )
    raw = "\n\n".join(pages_text)
    return OCRResult(
        document_id=doc_id,
        pages=pages,
        raw_text=raw,
        confidence=0.92,
        metadata=OCRMetadata(
            provider="test",
            model="mock",
            input_mime_type="text/plain",
            processing_time_ms=10.0,
        ),
    )


def _make_context(case_id) -> CaseContext:
    from datetime import datetime, timezone
    from src.normalization.canonical_models import CanonicalFact
    from src.knowledge_graph.graph_models import GraphProvenance
    doc_id = uuid4()
    prov = GraphProvenance(
        document_id=doc_id,
        confidence=0.85,
        parser_name="fixture",
        timestamp=datetime.now(timezone.utc),
        source_reference=SourceReference(document_id=doc_id, location=SourceLocation(page_number=1)),
    )
    fact = CanonicalFact(
        value="Victim sustained laceration injury on leg in vehicular accident",
        source_document_ids=(doc_id,),
        references=(prov,),
        source_path="medical.injuries",
        confidence=0.85,
        extraction_method="fixture",
        timestamp=prov.timestamp,
    )
    return CaseContext(
        case_id=case_id,
        medical_findings=(fact,),
        validation_disposition="draft_allowed",
    )


class TestRAGChunkingAndProvenance:
    def test_chunker_preserves_provenance(self):
        case_id = uuid4()
        doc = _make_source_doc(case_id, "panchnama.txt")
        text = (
            "Line 1: Spot panchnama recorded at intersection.\n"
            "Line 2: Skid marks measuring 14.5 meters were observed.\n"
            "\n"
            "Line 4: Broken headlight glass collected from the asphalt.\n"
            "Line 5: Blood stains found near pedestrian zebra crossing."
        )
        ocr = _make_ocr_result(doc.id, [text])

        chunker = DocumentChunker(target_chunk_words=50)
        chunks = chunker.chunk_document(case_id, doc, ocr)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.case_id == case_id
            assert chunk.document_id == doc.id
            assert chunk.original_filename == "panchnama.txt"
            assert chunk.page_number == 1
            assert chunk.line_range[0] >= 1
            assert chunk.line_range[1] >= chunk.line_range[0]
            assert chunk.source_reference.document_id == doc.id
            assert chunk.source_reference.location.page_number == 1
            assert chunk.token_count > 0


class TestCaseIsolation:
    def test_case_a_cannot_retrieve_case_b_passages(self, tmp_path: Path):
        case_a = uuid4()
        case_b = uuid4()

        doc_a = _make_source_doc(case_a, "case_a_statement.txt")
        doc_b = _make_source_doc(case_b, "case_b_statement.txt")

        ocr_a = _make_ocr_result(doc_a.id, ["Witness saw blue truck driving at high speed in Connaught Place."])
        ocr_b = _make_ocr_result(doc_b.id, ["Witness saw red motorcycle driving recklessly in Mumbai Marine Drive."])

        retriever_a = CaseRetriever(tmp_path, case_a, embedding_provider=MockEmbeddingProvider())
        retriever_b = CaseRetriever(tmp_path, case_b, embedding_provider=MockEmbeddingProvider())

        retriever_a.index_documents([doc_a], [(doc_a.id, ocr_a)])
        retriever_b.index_documents([doc_b], [(doc_b.id, ocr_b)])

        # Search in Case A for terms from Case B
        results_a = retriever_a.retrieve("Mumbai Marine Drive motorcycle")
        assert len(results_a) == 0

        # Querying Case A with Case B target must raise CaseIsolationViolationError
        with pytest.raises(CaseIsolationViolationError):
            retriever_a.retrieve("blue truck", target_case_id=case_b)

        # Cross check Case A search
        found_a = retriever_a.retrieve("blue truck speed Connaught")
        assert len(found_a) >= 1
        assert found_a[0].document_name == "case_a_statement.txt"
        assert found_a[0].document_id == doc_a.id

    def test_missing_or_corrupt_index_handled_gracefully(self, tmp_path: Path):
        case_id = uuid4()
        retriever = CaseRetriever(tmp_path, case_id)
        # Empty index
        assert len(retriever.chunks) == 0
        assert retriever.retrieve("any query") == ()

        # Corrupt file
        retriever.index_path.parent.mkdir(parents=True, exist_ok=True)
        retriever.index_path.write_text("{malformed json corrupt", encoding="utf-8")
        corrupt_retriever = CaseRetriever(tmp_path, case_id)
        assert len(corrupt_retriever.chunks) == 0
        assert corrupt_retriever.retrieve("any query") == ()


class TestRetrievalGuardrailsAndContradictions:
    def test_empty_and_irrelevant_queries_fallback_safely(self, tmp_path: Path):
        case_id = uuid4()
        doc = _make_source_doc(case_id, "inspection.txt")
        ocr = _make_ocr_result(doc.id, ["Brake test showed functioning hydraulic fluid and intact lining."])

        retriever = CaseRetriever(tmp_path, case_id, embedding_provider=NoOpEmbeddingProvider())
        retriever.index_documents([doc], [(doc.id, ocr)])

        assert retriever.retrieve("") == ()
        assert retriever.retrieve("   ") == ()
        assert retriever.retrieve("quantum physics astronaut satellite orbit") == ()

    def test_contradictory_passages_trigger_review_and_conflict(self, tmp_path: Path):
        case_id = uuid4()
        doc = _make_source_doc(case_id, "exculpatory_witness.txt")
        # Witness claims driver was driving slowly and stopped at signal (contradicts rash/negligent driving)
        ocr = _make_ocr_result(
            doc.id,
            ["Witness statement: The driver was not rash and was driving slowly at normal speed, stopped at green signal."]
        )

        retriever = CaseRetriever(tmp_path, case_id, embedding_provider=MockEmbeddingProvider())
        retriever.index_documents([doc], [(doc.id, ocr)])

        passages = retriever.retrieve("rash negligent speed")
        assert len(passages) >= 1
        assert passages[0].relevance_category == RelevanceCategory.CONTRADICTING

    def test_semantic_similarity_alone_never_marks_ingredient_as_supported(self, tmp_path: Path):
        """Rule: Semantic similarity alone must never mark an ingredient as established."""
        case_id = uuid4()
        doc = _make_source_doc(case_id, "statement.txt")
        ocr = _make_ocr_result(
            doc.id,
            ["Witness stated vehicle hit the victim causing severe impact on the leg."]
        )

        retriever = CaseRetriever(tmp_path, case_id, embedding_provider=MockEmbeddingProvider())
        retriever.index_documents([doc], [(doc.id, ocr)])

        # Set up a CaseContext with NO structured evidence
        context = _make_context(case_id)

        ref_path = Path(__file__).resolve().parent.parent / "references" / "legal" / "bns_sections.json"
        provider = LocalLegalReferenceProvider.load(ref_path, "bns-2023-2024-07-01")
        reasoner = LegalReasoner(provider, retriever=retriever)

        findings = reasoner.reason(context)
        # Any ingredient that only matched via RAG must be REQUIRES_REVIEW, not SUPPORTED!
        for f in findings.findings:
            for ing in f.ingredient_assessments:
                assert ing.status != IngredientStatus.SUPPORTED

    def test_controlled_dataset_finite_allowlist_preserved(self, tmp_path: Path):
        """RAG cannot introduce statutory sections outside the controlled reference dataset."""
        case_id = uuid4()
        doc = _make_source_doc(case_id, "irrelevant.txt")
        ocr = _make_ocr_result(doc.id, [
            "Accused was driving rashly on public road. Also discusses arbitrary foreign tax code section 404 and international piracy statute 999."
        ])

        retriever = CaseRetriever(tmp_path, case_id, embedding_provider=MockEmbeddingProvider())
        retriever.index_documents([doc], [(doc.id, ocr)])

        context = _make_context(case_id)
        ref_path = Path(__file__).resolve().parent.parent / "references" / "legal" / "bns_sections.json"
        provider = LocalLegalReferenceProvider.load(ref_path, "bns-2023-2024-07-01")
        reasoner = LegalReasoner(provider, retriever=retriever)

        findings = reasoner.reason(context)
        allowed_sections = {r.section_number for r in provider.dataset.references}
        assert len(findings.findings) > 0
        for f in findings.findings:
            assert f.proposed_section in allowed_sections
            assert f.proposed_section not in ("404", "999")


class TestPDFGenerationAndReviewerFlowWithRAG:
    def test_pdf_renders_with_retrieved_passages(self, tmp_path: Path):
        case_id = uuid4()
        doc = _make_source_doc(case_id, "statement.txt")
        ocr = _make_ocr_result(
            doc.id,
            ["Eye-witness saw accused driving rashly and hitting pedestrian."]
        )

        retriever = CaseRetriever(tmp_path, case_id, embedding_provider=MockEmbeddingProvider())
        retriever.index_documents([doc], [(doc.id, ocr)])

        context = _make_context(case_id)
        ref_path = Path(__file__).resolve().parent.parent / "references" / "legal" / "bns_sections.json"
        provider = LocalLegalReferenceProvider.load(ref_path, "bns-2023-2024-07-01")
        reasoner = LegalReasoner(provider, retriever=retriever)

        findings = reasoner.reason(context)
        populator = ChargeSheetPopulator()
        cs_data = populator.populate(context, findings)

        renderer = IF5Renderer()
        pdf_path = tmp_path / "test_chargesheet.pdf"
        out = renderer.render(cs_data, pdf_path, final=False)
        assert out.is_file()
        assert out.stat().st_size > 5000
