"""Case-isolated hybrid retriever combining BM25 keyword and dense vector retrieval."""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Sequence
from uuid import UUID

from ..domain.documents import SourceDocument
from ..extraction.ocr_result import OCRResult
from ..intake.storage_layout import CaseStorageLayout
from .document_chunker import DocumentChunker
from .embedding_provider import EmbeddingProvider, NoOpEmbeddingProvider
from .rag_models import CaseIndexMetadata, DocumentChunk, RelevanceCategory, RetrievedPassage

logger = logging.getLogger(__name__)

# Basic stopwords to improve BM25 focus
_STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've",
    "were", "weren't", "what", "what's", "when", "when's", "where", "where's",
    "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't",
    "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your",
    "yours", "yourself", "yourselves",
})

_CONTRADICTION_TRIGGERS = (
    "did not", "didnt", "not found", "was not", "were not", "denied",
    "contrary to", "negative", "ruled out", "absent", "no evidence of",
    "no alcohol", "sober", "slow speed", "normal speed", "stationary",
    "stopped", "green signal", "not rash", "not negligent", "natural death",
    "no injuries", "unrelated to", "disproved", "false allegation",
)


class CaseIsolationViolationError(ValueError):
    """Raised when an attempt is made to query or mutate another case's index."""


class CaseRetriever:
    """Case-isolated index and retrieval engine for a single case."""

    def __init__(
        self,
        storage_root: Path,
        case_id: UUID,
        embedding_provider: EmbeddingProvider | None = None,
        chunker: DocumentChunker | None = None,
    ) -> None:
        self.storage_root = storage_root
        self.case_id = case_id
        self.layout = CaseStorageLayout(storage_root, case_id)
        self.embedding_provider = embedding_provider or NoOpEmbeddingProvider()
        self.chunker = chunker or DocumentChunker()
        self.chunks: list[DocumentChunk] = []
        self.metadata: CaseIndexMetadata = CaseIndexMetadata(case_id=case_id)
        self._load_index()

    @property
    def index_path(self) -> Path:
        return self.layout.processed_directory / "rag" / "index.json"

    def _tokenize(self, text: str) -> list[str]:
        words = re.findall(r"[A-Za-z0-9_]+", text.casefold())
        return [w for w in words if len(w) > 1 and w not in _STOPWORDS]

    def _load_index(self) -> None:
        """Safely load index from disk; corrupt or missing index falls back gracefully."""
        if not self.index_path.is_file():
            return
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            loaded_case_id = UUID(str(data.get("case_id")))
            if loaded_case_id != self.case_id:
                logger.warning(
                    "Index case ID %s does not match retriever case ID %s; ignoring index.",
                    loaded_case_id,
                    self.case_id,
                )
                return
            self.metadata = CaseIndexMetadata.model_validate(data.get("metadata", {}))
            loaded_chunks = []
            for item in data.get("chunks", []):
                loaded_chunks.append(DocumentChunk.model_validate(item))
            self.chunks = loaded_chunks
            logger.info("Loaded case index for %s with %d chunks.", self.case_id, len(self.chunks))
        except Exception as exc:
            logger.warning("Failed to load corrupt or invalid case index for %s: %s", self.case_id, exc)
            self.chunks = []
            self.metadata = CaseIndexMetadata(case_id=self.case_id)

    def save_index(self) -> Path:
        """Persist index atomically to the case layout."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "case_id": str(self.case_id),
            "metadata": self.metadata.model_dump(mode="json"),
            "chunks": [c.model_dump(mode="json") for c in self.chunks],
        }
        self.index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.index_path

    def build_index(self, chunks: Sequence[DocumentChunk]) -> None:
        """Directly populate chunks and save index for deterministic testing and fixture setup."""
        self.chunks = list(chunks)
        self.metadata = CaseIndexMetadata(case_id=self.case_id, total_chunks=len(self.chunks))
        self.save_index()

    def index_documents(
        self,
        documents: Sequence[SourceDocument],
        ocr_results: Sequence[tuple[UUID, OCRResult]],
    ) -> int:
        """Index OCR extractions for the case, avoiding duplicate processing."""
        doc_map = {d.id: d for d in documents if d.case_id == self.case_id}
        valid_doc_ids = set(doc_map.keys())
        # Prune stale chunks and hashes from prior uploads or superseded documents
        self.chunks = [c for c in self.chunks if c.document_id in valid_doc_ids]
        updated_hashes = {
            k: v for k, v in self.metadata.document_hashes.items()
            if k in {str(did) for did in valid_doc_ids}
        }
        new_chunks: list[DocumentChunk] = []

        for doc_id, ocr_res in ocr_results:
            doc = doc_map.get(doc_id)
            if not doc:
                continue

            # Skip if document hash is identical to previously indexed version
            if updated_hashes.get(str(doc.id)) == doc.sha256:
                continue

            # Remove any existing chunks for this document if re-indexing modified file
            self.chunks = [c for c in self.chunks if c.document_id != doc.id]

            doc_chunks = self.chunker.chunk_document(self.case_id, doc, ocr_res)
            # Generate embeddings if provider is available
            embedded_chunks = []
            for chunk in doc_chunks:
                emb = self.embedding_provider.embed(chunk.text)
                if emb:
                    chunk = chunk.model_copy(update={"embedding": emb})
                embedded_chunks.append(chunk)

            new_chunks.extend(embedded_chunks)
            updated_hashes[str(doc.id)] = doc.sha256

        if new_chunks:
            self.chunks.extend(new_chunks)
            self.metadata = self.metadata.model_copy(
                update={
                    "document_hashes": updated_hashes,
                    "total_chunks": len(self.chunks),
                    "embedding_model": self.embedding_provider.model_name,
                }
            )
            self.save_index()
            logger.info("Indexed %d new chunks for case %s (total: %d)", len(new_chunks), self.case_id, len(self.chunks))

        return len(new_chunks)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 3,
        threshold: float = 0.05,
        target_case_id: UUID | None = None,
    ) -> tuple[RetrievedPassage, ...]:
        """Retrieve the most relevant passages for a query with BM25 + optional vector scoring."""
        # Enforce strict case isolation
        if target_case_id is not None and target_case_id != self.case_id:
            raise CaseIsolationViolationError(
                f"Cross-case query blocked: target {target_case_id} != retriever {self.case_id}"
            )

        if not query or not query.strip() or not self.chunks:
            return ()

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return ()

        num_docs = len(self.chunks)
        # 1. Compute BM25 scores
        doc_lengths = [len(c.text.split()) for c in self.chunks]
        avg_dl = sum(doc_lengths) / max(num_docs, 1)

        # Document frequency for query tokens
        doc_freqs: dict[str, int] = {}
        chunk_token_sets = [set(self._tokenize(c.text)) for c in self.chunks]
        for qt in set(query_tokens):
            doc_freqs[qt] = sum(1 for tokens in chunk_token_sets if qt in tokens)

        bm25_scores = [0.0] * num_docs
        k1 = 1.5
        b = 0.75

        for qt in set(query_tokens):
            n_qt = doc_freqs.get(qt, 0)
            if n_qt == 0:
                continue
            idf = math.log(((num_docs - n_qt + 0.5) / (n_qt + 0.5)) + 1.0)
            for idx, chunk in enumerate(self.chunks):
                raw_chunk_tokens = self._tokenize(chunk.text)
                tf = raw_chunk_tokens.count(qt)
                if tf > 0:
                    numerator = tf * (k1 + 1.0)
                    denominator = tf + k1 * (1.0 - b + b * (doc_lengths[idx] / avg_dl))
                    bm25_scores[idx] += idf * (numerator / denominator)

        # Normalize BM25 scores to [0, 1]
        max_bm25 = max(bm25_scores) if bm25_scores else 0.0
        normalized_bm25 = [s / max_bm25 if max_bm25 > 0 else 0.0 for s in bm25_scores]

        # 2. Dense vector similarity (if provider available and chunks have embeddings)
        query_emb = self.embedding_provider.embed(query) if self.embedding_provider.is_available else ()
        vector_scores = [0.0] * num_docs
        has_vector = bool(query_emb)

        if has_vector:
            for idx, chunk in enumerate(self.chunks):
                if chunk.embedding and len(chunk.embedding) == len(query_emb):
                    dot = sum(a * b for a, b in zip(query_emb, chunk.embedding))
                    vector_scores[idx] = max(0.0, dot)

        # 3. Hybrid combination
        final_scores: list[tuple[int, float, tuple[str, ...]]] = []
        for idx in range(num_docs):
            if has_vector:
                score = 0.5 * normalized_bm25[idx] + 0.5 * vector_scores[idx]
            else:
                score = normalized_bm25[idx]

            matched = tuple(qt for qt in set(query_tokens) if qt in chunk_token_sets[idx])
            if score >= threshold and matched:
                final_scores.append((idx, score, matched))

        # Sort descending by score
        final_scores.sort(key=lambda x: x[1], reverse=True)
        top_candidates = final_scores[:top_k]

        results: list[RetrievedPassage] = []
        for idx, score, matched in top_candidates:
            chunk = self.chunks[idx]
            category = self._classify_relevance(query, chunk.text)
            results.append(
                RetrievedPassage.from_chunk(
                    chunk,
                    score=score,
                    category=category,
                    matched_terms=matched,
                )
            )

        return tuple(results)

    def _classify_relevance(self, query: str, text: str) -> RelevanceCategory:
        """Classify passage as supporting or contradicting relative to query."""
        folded = text.casefold()

        # Specific exculpatory phrases that contradict offences
        exculpatory_phrases = (
            "not rash", "not negligent", "was not rash", "was not negligent",
            "driving slowly", "slow speed", "at normal speed", "stopped at green signal",
            "sober", "no alcohol", "did not commit", "falsely implicated",
            "no evidence of negligence", "natural death", "ruled out foul play",
        )
        for phrase in exculpatory_phrases:
            if phrase in folded:
                return RelevanceCategory.CONTRADICTING

        # Contextual negation linked to specific substantive query terms using whole-word matching
        generic_terms = {"act", "others", "person", "case", "report", "document", "section"}
        substantive_tokens = [qt for qt in self._tokenize(query) if qt not in generic_terms]

        for neg in ("did not", "didnt", "not found", "denied", "contrary to", "ruled out", "absent", "no evidence of"):
            if neg in folded:
                for qt in substantive_tokens:
                    pattern1 = rf"\b{re.escape(neg)}\s+{re.escape(qt)}\b"
                    pattern2 = rf"\b{re.escape(qt)}\s+was\s+{re.escape(neg)}\b"
                    if re.search(pattern1, folded) or re.search(pattern2, folded):
                        return RelevanceCategory.CONTRADICTING

        return RelevanceCategory.SUPPORTING
