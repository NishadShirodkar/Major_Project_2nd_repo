"""Workflow stage for evidence-backed, non-final legal recommendations."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from uuid import UUID

from ..config import Config
from ..intake.storage_layout import CaseStorageLayout
from ..rag.case_retriever import CaseRetriever
from ..rag.embedding_provider import EmbeddingProvider, GeminiEmbeddingProvider, NoOpEmbeddingProvider
from ..workflow.context import ContextItem, GeneratedArtifact, WorkflowContext
from ..workflow.stage import WorkflowStage
from .legal_artifacts import LegalArtifactWriter
from .legal_reasoner import LegalReasoner

logger = logging.getLogger(__name__)


class LegalReasoningStage(WorkflowStage):
    name = "legal_reasoning"

    def __init__(
        self,
        storage_root: Path,
        reasoner: LegalReasoner,
        artifact_writer: LegalArtifactWriter | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.storage_root = storage_root
        self.reasoner = reasoner
        self.artifact_writer = artifact_writer or LegalArtifactWriter(storage_root)
        self.embedding_provider = embedding_provider

    def can_run(self, context: WorkflowContext) -> bool:
        return context.case_context is not None and context.legal_findings is None

    def execute(self, context: WorkflowContext) -> WorkflowContext:
        started = time.perf_counter()
        if context.case_context is None:
            raise ValueError("Legal reasoning requires a CaseContext")

        # Initialize case-isolated retriever and index OCR documents
        retriever: CaseRetriever | None = None
        rag_artifacts: tuple[GeneratedArtifact, ...] = ()
        try:
            if self.embedding_provider is not None:
                emb_provider = self.embedding_provider
            elif Config.GEMINI_API_KEY:
                emb_provider = GeminiEmbeddingProvider(Config.GEMINI_API_KEY)
            else:
                emb_provider = NoOpEmbeddingProvider()
            retriever = CaseRetriever(self.storage_root, context.case_id, embedding_provider=emb_provider)
            if not context.resume:
                from ..rag.rag_models import CaseIndexMetadata
                retriever.chunks = []
                retriever.metadata = CaseIndexMetadata(case_id=context.case_id)
            ocr_pairs: list[tuple[UUID, Any]] = []
            for item in context.ocr_results:
                if hasattr(item.value, "document_id"):
                    ocr_pairs.append((item.value.document_id, item.value))
            if ocr_pairs and context.uploaded_documents:
                retriever.index_documents(context.uploaded_documents, ocr_pairs)
                if retriever.index_path.is_file():
                    layout = CaseStorageLayout(self.storage_root, context.case_id)
                    rag_artifacts = (
                        GeneratedArtifact(
                            name="rag_index",
                            storage_key=layout.relative_key(retriever.index_path),
                            media_type="application/json",
                        ),
                    )
        except Exception as exc:
            logger.warning("Case-isolated RAG indexing failed; proceeding with deterministic reasoning: %s", exc)
            retriever = None

        findings = self.reasoner.reason(context.case_context, retriever=retriever)
        metrics = {
            "reasoning_duration_ms": (time.perf_counter() - started) * 1000,
            "findings": len(findings.findings),
            "supported_findings": sum(item.status.value == "supported" for item in findings.findings),
            "insufficient_findings": sum(item.status.value == "insufficient_evidence" for item in findings.findings),
            "conflicted_findings": sum(item.status.value == "conflicted" for item in findings.findings),
            "requiring_review": sum(item.review_required for item in findings.findings),
            "llm_retry_count": findings.retry_count,
            "rag_chunks_indexed": len(retriever.chunks) if retriever else 0,
        }
        return context.with_updates(
            legal_findings=findings,
            generated_artifacts=context.generated_artifacts + self.artifact_writer.write(context.case_context, findings) + rag_artifacts,
            stage_metrics=context.stage_metrics + (ContextItem(key=self.name, value=metrics),),
            execution_metadata=context.execution_metadata + (ContextItem(key=self.name, value={"review_required": findings.review_required}),),
        )
