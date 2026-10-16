"""Domain models for case-isolated document chunking and passage retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid5, NAMESPACE_URL

from pydantic import Field

from ..domain.common import DomainModel, SourceLocation, SourceReference, ConfidenceLevel


class RelevanceCategory(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    INCONCLUSIVE = "inconclusive"


class DocumentChunk(DomainModel):
    """A semantic passage extracted from an OCR page preserving full provenance."""

    chunk_id: UUID
    case_id: UUID
    document_id: UUID
    original_filename: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    line_range: tuple[int, int] = (1, 1)
    text: str = Field(min_length=1)
    token_count: int = Field(ge=0, default=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_reference: SourceReference
    embedding: tuple[float, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        case_id: UUID,
        document_id: UUID,
        original_filename: str,
        page_number: int,
        line_start: int,
        line_end: int,
        text: str,
        confidence: float | None = None,
        embedding: tuple[float, ...] = (),
        chunk_index: int = 0,
    ) -> "DocumentChunk":
        chunk_uuid = uuid5(
            NAMESPACE_URL,
            f"byomkesh-chunk:{case_id}:{document_id}:{page_number}:{line_start}:{line_end}:{chunk_index}",
        )
        conf_level = ConfidenceLevel.HIGH if (confidence or 0.8) >= 0.8 else ConfidenceLevel.MEDIUM
        source_ref = SourceReference(
            document_id=document_id,
            location=SourceLocation(
                page_number=page_number,
                extraction_key=f"p{page_number}_lines_{line_start}_{line_end}",
            ),
            excerpt=text[:160],
            confidence=conf_level,
        )
        words = text.split()
        return cls(
            chunk_id=chunk_uuid,
            case_id=case_id,
            document_id=document_id,
            original_filename=original_filename,
            page_number=page_number,
            line_range=(line_start, line_end),
            text=text,
            token_count=len(words),
            confidence=confidence,
            source_reference=source_ref,
            embedding=embedding,
        )


class RetrievedPassage(DomainModel):
    """A scored passage retrieved from the case index for a query."""

    chunk_id: UUID
    document_id: UUID
    document_name: str
    page_number: int
    line_range: tuple[int, int]
    text: str
    relevance_score: float = Field(ge=0.0)
    relevance_category: RelevanceCategory = RelevanceCategory.SUPPORTING
    matched_terms: tuple[str, ...] = ()
    source_reference: SourceReference

    @classmethod
    def from_chunk(
        cls,
        chunk: DocumentChunk,
        *,
        score: float,
        category: RelevanceCategory = RelevanceCategory.SUPPORTING,
        matched_terms: tuple[str, ...] = (),
    ) -> "RetrievedPassage":
        return cls(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_name=chunk.original_filename,
            page_number=chunk.page_number,
            line_range=chunk.line_range,
            text=chunk.text,
            relevance_score=round(score, 4),
            relevance_category=category,
            matched_terms=matched_terms,
            source_reference=chunk.source_reference,
        )


class CaseIndexMetadata(DomainModel):
    """Metadata tracking document state and index integrity for a case."""

    case_id: UUID
    document_hashes: dict[str, str] = Field(default_factory=dict)
    total_chunks: int = Field(ge=0, default=0)
    indexed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    embedding_model: str | None = None
    version: str = "1.0"
