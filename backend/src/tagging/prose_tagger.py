"""Phase 2 prose fact tagging with LLM proposal and verbatim OCR quote verification."""

from __future__ import annotations

import json
from typing import Any, Protocol

from ..extraction.ocr_result import OCRResult
from ..normalization.canonical_models import CanonicalFact, CanonicalInvestigation


class ProseTaggingClient(Protocol):
    def generate_json(self, prompt: str) -> dict[str, Any]: ...


class ProseTagger:
    """Proposes fact tags from unstructured prose and verifies quotes against OCR text."""

    def __init__(
        self,
        client: ProseTaggingClient | None = None,
        vocabulary: set[str] | None = None,
    ) -> None:
        self.client = client
        self.vocabulary = vocabulary or set()

    def tag_investigation(
        self,
        canonical: CanonicalInvestigation,
        ocr_results: dict[str, OCRResult],
    ) -> CanonicalInvestigation:
        if self.client is None or not ocr_results:
            return canonical

        # Assemble full text per document for quote verification
        doc_texts: dict[str, str] = {
            doc_id: res.raw_text
            for doc_id, res in ocr_results.items()
        }

        # Prompt LLM to propose tags with exact quotes
        prompt = json.dumps({
            "task": "Extract evidence-backed fact tags from investigation prose",
            "fact_tag_vocabulary": list(self.vocabulary),
            "documents": [
                {
                    "document_id": doc_id,
                    "text": text[:4000],  # bounded per document
                }
                for doc_id, text in doc_texts.items()
            ],
            "schema": {
                "proposed_tags": [
                    {
                        "document_id": "string",
                        "tag": "string (must be from vocabulary)",
                        "verbatim_quote": "exact substring from text",
                    }
                ]
            }
        })

        try:
            response = self.client.generate_json(prompt)
            proposals = response.get("proposed_tags", [])
        except Exception:
            return canonical

        # Filter: quote must exist verbatim in OCR text and tag must be in vocabulary
        verified_tags_by_doc: dict[str, set[str]] = {}
        for p in proposals:
            tag = p.get("tag")
            doc_id = p.get("document_id")
            quote = p.get("verbatim_quote")
            if not tag or not doc_id or not quote:
                continue
            if tag not in self.vocabulary:
                continue
            full_text = doc_texts.get(doc_id, "")
            if quote.casefold() in full_text.casefold():
                verified_tags_by_doc.setdefault(doc_id, set()).add(tag)

        if not verified_tags_by_doc:
            return canonical

        # Attach verified tags to canonical timeline and evidence facts associated with that document
        def update_fact(fact: CanonicalFact) -> CanonicalFact:
            tags_to_add: set[str] = set()
            for doc_uuid in fact.source_document_ids:
                doc_str = str(doc_uuid)
                if doc_str in verified_tags_by_doc:
                    tags_to_add.update(verified_tags_by_doc[doc_str])
            if tags_to_add:
                combined = tuple(dict.fromkeys((*fact.tags, *tags_to_add)))
                return fact.model_copy(update={"tags": combined})
            return fact

        updated_timeline = tuple(
            event.model_copy(update={"description": update_fact(event.description)})
            for event in canonical.timeline
        )
        updated_evidence = tuple(
            item.model_copy(update={"description": update_fact(item.description)})
            for item in canonical.evidence
        )

        return canonical.model_copy(update={
            "timeline": updated_timeline,
            "evidence": updated_evidence,
        })

