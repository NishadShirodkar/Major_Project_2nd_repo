"""Case-isolated RAG and passage retrieval package."""

from .rag_models import (
    DocumentChunk,
    RetrievedPassage,
    RelevanceCategory,
    CaseIndexMetadata,
)
from .document_chunker import DocumentChunker
from .embedding_provider import (
    EmbeddingProvider,
    GeminiEmbeddingProvider,
    MockEmbeddingProvider,
    NoOpEmbeddingProvider,
)
from .case_retriever import CaseRetriever, CaseIsolationViolationError

__all__ = [
    "DocumentChunk",
    "RetrievedPassage",
    "RelevanceCategory",
    "CaseIndexMetadata",
    "DocumentChunker",
    "EmbeddingProvider",
    "GeminiEmbeddingProvider",
    "MockEmbeddingProvider",
    "NoOpEmbeddingProvider",
    "CaseRetriever",
    "CaseIsolationViolationError",
]
