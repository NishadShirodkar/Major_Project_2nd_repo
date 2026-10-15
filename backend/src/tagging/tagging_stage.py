"""Workflow stage for evidence fact tagging between canonicalization and validation."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from ..intake.storage_layout import CaseStorageLayout
from ..legal.legal_rules import LegalReferenceProvider
from ..workflow.context import ContextItem, GeneratedArtifact, WorkflowContext
from ..workflow.stage import WorkflowStage
from .deterministic_tagger import DeterministicTagger
from .prose_tagger import ProseTagger, ProseTaggingClient


class FactTaggingStage(WorkflowStage):
    name = "fact_tagging"

    def __init__(
        self,
        storage_root: Path,
        *,
        reference_provider: LegalReferenceProvider | None = None,
        prose_client: ProseTaggingClient | None = None,
    ) -> None:
        self.storage_root = storage_root
        self.reference_provider = reference_provider
        self.prose_client = prose_client

    def can_run(self, context: WorkflowContext) -> bool:
        return context.canonical_investigation is not None

    def execute(self, context: WorkflowContext) -> WorkflowContext:
        started = time.perf_counter()
        canonical = context.canonical_investigation
        if canonical is None:
            raise ValueError("Fact tagging requires a CanonicalInvestigation")

        vocab: set[str] = set()
        if self.reference_provider and hasattr(self.reference_provider, "dataset"):
            vocab = set(self.reference_provider.dataset.fact_tag_vocabulary.keys())

        # Phase 1: Deterministic tagging
        det_tagger = DeterministicTagger(vocab)
        tagged_canonical = det_tagger.tag_investigation(canonical)

        # Phase 2: Prose LLM tagging with quote verification
        if self.prose_client is not None and context.ocr_results:
            ocr_dict = {
                item.key.removeprefix("ocr:"): item.value
                for item in context.ocr_results
            }
            prose_tagger = ProseTagger(self.prose_client, vocab)
            tagged_canonical = prose_tagger.tag_investigation(tagged_canonical, ocr_dict)

        # Collect tag summary
        facts = [
            *tagged_canonical.medical_findings,
            *tagged_canonical.forensic_findings,
            *(p.name for p in tagged_canonical.accused),
            *(e.description for e in tagged_canonical.evidence),
            *(r.description for r in tagged_canonical.recovered_property),
            *(v.registration_number for v in tagged_canonical.vehicles),
            *(ev.description for ev in tagged_canonical.timeline),
        ]
        tag_counts: dict[str, int] = {}
        tagged_facts_count = 0
        tag_dump: list[dict[str, Any]] = []
        for f in facts:
            if f.tags:
                tagged_facts_count += 1
                for t in f.tags:
                    tag_counts[t] = tag_counts.get(t, 0) + 1
                tag_dump.append({
                    "source_path": f.source_path,
                    "value": str(f.value)[:100],
                    "tags": list(f.tags),
                })

        # Write fact_tags.json artifact
        layout = CaseStorageLayout(self.storage_root, context.case_id).ensure_exists()
        dir_path = layout.processed_directory / "legal"
        dir_path.mkdir(parents=True, exist_ok=True)
        artifact_path = dir_path / "fact_tags.json"
        artifact_path.write_text(
            json.dumps({"tag_counts": tag_counts, "tagged_facts": tag_dump}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        artifact = GeneratedArtifact(
            name="fact_tags",
            storage_key=layout.relative_key(artifact_path),
            media_type="application/json",
        )

        duration_ms = (time.perf_counter() - started) * 1000
        metrics = {
            "duration_ms": duration_ms,
            "tagged_facts_count": tagged_facts_count,
            "distinct_tags": len(tag_counts),
        }

        return context.with_updates(
            canonical_investigation=tagged_canonical,
            generated_artifacts=context.generated_artifacts + (artifact,),
            stage_metrics=context.stage_metrics + (ContextItem(key=self.name, value=metrics),),
            execution_metadata=context.execution_metadata + (ContextItem(key=self.name, value={"distinct_tags": len(tag_counts)}),),
        )

