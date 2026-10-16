"""Workflow stage that independently parses completed OCR results by registry lookup."""

from __future__ import annotations

import re
import time
from pathlib import Path
from uuid import UUID

from ..domain.documents import ClassificationStatus, DocumentType, ExtractionState, ParsingState
from ..extraction.ocr_result import OCRResult
from ..intake.document_classifier import DeterministicDocumentClassifier
from ..intake.storage_layout import CaseStorageLayout
from ..workflow.context import ContextItem, GeneratedArtifact, WorkflowContext
from ..workflow.stage import WorkflowStage
from .base_parser import ParserValidationError
from .parser_artifacts import ParsedDocumentArtifactWriter
from .parser_registry import ParserRegistry


class ParserStage(WorkflowStage):
    name = "document_parsing"

    def __init__(
        self,
        storage_root: Path,
        registry: ParserRegistry,
        artifact_writer: ParsedDocumentArtifactWriter | None = None,
        classifier: DeterministicDocumentClassifier | None = None,
        resume: bool = False,
    ) -> None:
        self.storage_root = storage_root
        self.registry = registry
        self.artifact_writer = artifact_writer or ParsedDocumentArtifactWriter(storage_root)
        self.classifier = classifier or DeterministicDocumentClassifier()
        self.resume = resume

    def can_run(self, context: WorkflowContext) -> bool:
        result_ids = {self._ocr_result(item).document_id for item in context.ocr_results if self._is_ocr_result(item)}
        return any(
            document.extraction_state == ExtractionState.COMPLETE
            and document.parsing_state in (ParsingState.PENDING, ParsingState.FAILED)
            and document.id in result_ids
            for document in context.uploaded_documents
        )

    def execute(self, context: WorkflowContext) -> WorkflowContext:
        started = time.perf_counter()
        ocr_results = {
            self._ocr_result(item).document_id: self._ocr_result(item)
            for item in context.ocr_results
            if self._is_ocr_result(item)
        }
        parsed_items = list(context.parsed_documents)
        artifacts = list(context.generated_artifacts)
        updated_documents = []
        retry_count = 0
        confidence_values: list[float] = []
        warnings: list[str] = []
        candidates_to_parse = 0

        for document in context.uploaded_documents:
            result = ocr_results.get(document.id)
            if (
                document.extraction_state != ExtractionState.COMPLETE
                or document.parsing_state not in (ParsingState.PENDING, ParsingState.FAILED)
                or result is None
            ):
                updated_documents.append(document)
                continue

            candidates_to_parse += 1
            current_type = document.detected_type
            current_status = document.classification_status
            current_confidence = document.classification_confidence

            # If document was classified as generic/OTHER or had unknown classification, try content-based refinement
            if (current_type == DocumentType.OTHER or current_status == ClassificationStatus.UNKNOWN) and result.raw_text:
                classification = self.classifier.classify_content(result.raw_text)
                if classification is not None:
                    current_type = classification.document_type
                    current_status = ClassificationStatus.CLASSIFIED
                    current_confidence = classification.confidence

            # Check for existing valid parsed document when resume mode is active
            stem = re.sub(r"[^A-Za-z0-9]+", "_", Path(document.original_filename).stem).strip("_") or "document"
            layout = CaseStorageLayout(self.storage_root, document.case_id)
            cached_path = layout.processed_directory / "parsed" / f"{stem}_{document.id.hex[:8]}.json"

            if self.resume and cached_path.is_file():
                try:
                    parser = self.registry.get(current_type)
                    parsed_document = parser.model_type.model_validate_json(cached_path.read_text(encoding="utf-8"))
                    parsed_items.append(ContextItem(key=str(document.id), value=parsed_document))
                    artifacts.append(
                        GeneratedArtifact(
                            name="parsed_document",
                            storage_key=layout.relative_key(cached_path),
                            media_type="application/json",
                        )
                    )
                    updated_documents.append(
                        document.model_copy(
                            update={
                                "detected_type": current_type,
                                "classification_status": current_status,
                                "classification_confidence": current_confidence,
                                "parsing_state": ParsingState.COMPLETE,
                            }
                        )
                    )
                    if parsed_document.parse_metadata.confidence is not None:
                        confidence_values.append(parsed_document.parse_metadata.confidence)
                    continue
                except Exception:
                    pass

            try:
                parser = self.registry.get(current_type)
                parsed_document = parser.parse(result)
                parsed_items.append(ContextItem(key=str(document.id), value=parsed_document))
                artifacts.append(self.artifact_writer.write(document, parsed_document))
                updated_documents.append(
                    document.model_copy(
                        update={
                            "detected_type": current_type,
                            "classification_status": current_status,
                            "classification_confidence": current_confidence,
                            "parsing_state": ParsingState.COMPLETE,
                        }
                    )
                )
                retry_count += parsed_document.parse_metadata.retry_count
                if parsed_document.parse_metadata.confidence is not None:
                    confidence_values.append(parsed_document.parse_metadata.confidence)
                warnings.extend(parsed_document.parse_metadata.warnings)
            except Exception as exc:
                warnings.append(f"Parsing failed for document {document.id} ({document.original_filename}): {exc}")
                updated_documents.append(
                    document.model_copy(
                        update={
                            "detected_type": current_type,
                            "classification_status": current_status,
                            "classification_confidence": current_confidence,
                            "parsing_state": ParsingState.FAILED,
                        }
                    )
                )

        parsed_count = len(parsed_items) - len(context.parsed_documents)
        if candidates_to_parse > 0 and parsed_count == 0:
            raise ParserValidationError(
                f"All {candidates_to_parse} candidate document(s) failed parsing: {'; '.join(warnings)}"
            )

        return context.with_updates(
            uploaded_documents=tuple(updated_documents),
            parsed_documents=tuple(parsed_items),
            generated_artifacts=tuple(artifacts),
            stage_metrics=context.stage_metrics + (
                ContextItem(
                    key=self.name,
                    value={
                        "parse_duration_ms": (time.perf_counter() - started) * 1000,
                        "validation_success": True,
                        "retry_count": retry_count,
                        "confidence": (sum(confidence_values) / len(confidence_values) if confidence_values else None),
                        "warnings": tuple(warnings),
                        "documents_parsed": parsed_count,
                    },
                ),
            ),
            execution_metadata=context.execution_metadata + (
                ContextItem(key=self.name, value={"documents_parsed": parsed_count}),
            ),
        )

    @staticmethod
    def _is_ocr_result(item: ContextItem) -> bool:
        return isinstance(item.value, OCRResult)

    @staticmethod
    def _ocr_result(item: ContextItem) -> OCRResult:
        if not isinstance(item.value, OCRResult):
            raise TypeError("OCR result context item must contain OCRResult")
        return item.value
