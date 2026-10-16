"""Processes OCR page extractions into provenance-preserving semantic chunks."""

from __future__ import annotations

import re
from typing import Sequence
from uuid import UUID

from ..domain.documents import SourceDocument
from ..extraction.ocr_result import OCRResult
from .rag_models import DocumentChunk


class DocumentChunker:
    """Extracts coherent, line-tracked chunks from OCR page extractions."""

    def __init__(self, target_chunk_words: int = 150, min_chunk_words: int = 15) -> None:
        self.target_chunk_words = target_chunk_words
        self.min_chunk_words = min_chunk_words

    def chunk_document(
        self,
        case_id: UUID,
        document: SourceDocument,
        ocr_result: OCRResult,
    ) -> tuple[DocumentChunk, ...]:
        """Convert all pages in an OCR result to line-bounded chunks."""
        chunks: list[DocumentChunk] = []

        for page in ocr_result.pages:
            page_chunks = self.chunk_page(
                case_id=case_id,
                document_id=document.id,
                original_filename=document.original_filename,
                page_number=page.page_number,
                page_text=page.text,
                page_confidence=page.confidence,
                start_index=len(chunks),
            )
            chunks.extend(page_chunks)

        return tuple(chunks)

    def chunk_page(
        self,
        *,
        case_id: UUID,
        document_id: UUID,
        original_filename: str,
        page_number: int,
        page_text: str,
        page_confidence: float | None = None,
        start_index: int = 0,
    ) -> list[DocumentChunk]:
        """Split a single OCR page into bounded paragraph chunks."""
        if not page_text or not page_text.strip():
            return []

        raw_lines = page_text.splitlines()
        if not raw_lines:
            return []

        # Group lines into paragraphs while retaining line numbers
        paragraphs: list[tuple[int, int, str]] = []  # (start_line, end_line, text)
        current_lines: list[str] = []
        start_line = 1

        for line_idx, line in enumerate(raw_lines, 1):
            stripped = line.strip()
            if not stripped:
                if current_lines:
                    text_block = " ".join(current_lines).strip()
                    if text_block:
                        paragraphs.append((start_line, line_idx - 1, text_block))
                    current_lines = []
                start_line = line_idx + 1
            else:
                if not current_lines:
                    start_line = line_idx
                current_lines.append(stripped)

        if current_lines:
            text_block = " ".join(current_lines).strip()
            if text_block:
                paragraphs.append((start_line, len(raw_lines), text_block))

        # Coalesce very small paragraphs or split oversized ones
        page_chunks: list[DocumentChunk] = []
        accumulator_lines: list[str] = []
        acc_start = 1
        acc_end = 1
        chunk_idx = start_index

        for p_start, p_end, p_text in paragraphs:
            word_count = len(p_text.split())

            # If accumulator is empty, start with current paragraph
            if not accumulator_lines:
                accumulator_lines.append(p_text)
                acc_start = p_start
                acc_end = p_end
            elif len(" ".join(accumulator_lines).split()) + word_count <= self.target_chunk_words:
                # Merge small adjacent paragraphs
                accumulator_lines.append(p_text)
                acc_end = p_end
            else:
                # Flush accumulator
                combined_text = " ".join(accumulator_lines).strip()
                if combined_text:
                    page_chunks.append(
                        DocumentChunk.create(
                            case_id=case_id,
                            document_id=document_id,
                            original_filename=original_filename,
                            page_number=page_number,
                            line_start=acc_start,
                            line_end=acc_end,
                            text=combined_text,
                            confidence=page_confidence,
                            chunk_index=chunk_idx,
                        )
                    )
                    chunk_idx += 1
                accumulator_lines = [p_text]
                acc_start = p_start
                acc_end = p_end

        # Flush trailing accumulator
        if accumulator_lines:
            combined_text = " ".join(accumulator_lines).strip()
            if combined_text:
                page_chunks.append(
                    DocumentChunk.create(
                        case_id=case_id,
                        document_id=document_id,
                        original_filename=original_filename,
                        page_number=page_number,
                        line_start=acc_start,
                        line_end=acc_end,
                        text=combined_text,
                        confidence=page_confidence,
                        chunk_index=chunk_idx,
                    )
                )

        return page_chunks
