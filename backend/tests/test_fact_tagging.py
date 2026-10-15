"""Unit tests for deterministic and prose fact tagging."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from uuid import UUID, uuid4

from src.domain.common import SourceReference
from src.extraction.ocr_result import OCRMetadata, OCRPage, OCRResult
from src.knowledge_graph.graph_models import GraphProvenance
from src.normalization.canonical_models import (
    CanonicalEvidence,
    CanonicalFact,
    CanonicalInvestigation,
    CanonicalPerson,
    CanonicalTimelineEvent,
    CanonicalVehicle,
    CanonicalCaseMetadata,
    ConfidenceSummary,
)
from src.tagging.deterministic_tagger import DeterministicTagger
from src.tagging.prose_tagger import ProseTagger
from src.tagging.tagging_stage import FactTaggingStage
from src.workflow.context import ContextItem, WorkflowContext
from src.workflow.state import WorkflowState


def make_fact(value: str, path: str = "fixture.path", doc_id: UUID | None = None) -> CanonicalFact:
    d_id = doc_id or uuid4()
    prov = GraphProvenance(
        document_id=d_id,
        confidence=0.85,
        parser_name="fixture",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_reference=SourceReference(document_id=d_id),
    )
    return CanonicalFact(
        value=value,
        source_document_ids=(d_id,),
        references=(prov,),
        source_path=path,
        confidence=0.85,
        extraction_method="fixture",
        timestamp=prov.timestamp,
    )


class MockProseClient:
    def __init__(self, proposals: list[dict]):
        self.proposals = proposals

    def generate_json(self, prompt: str):
        return {"proposed_tags": self.proposals}


class FactTaggingTests(TestCase):
    def test_negative_injury_does_not_tag_injury_documented(self):
        vocab = {"injury.documented", "injury.bodily_pain"}
        tagger = DeterministicTagger(vocab)

        # "no injury found"
        canonical = CanonicalInvestigation(
            case_metadata=CanonicalCaseMetadata(case_id=uuid4()),
            medical_findings=(make_fact("Patient examined. No visible injury found on body."),),
            confidence_summary=ConfidenceSummary(fact_count=1),
        )
        tagged = tagger.tag_investigation(canonical)
        self.assertEqual(tagged.medical_findings[0].tags, ())

        # "no external injury"
        canonical2 = CanonicalInvestigation(
            case_metadata=CanonicalCaseMetadata(case_id=uuid4()),
            medical_findings=(make_fact("No external injury seen. Patient discharged."),),
            confidence_summary=ConfidenceSummary(fact_count=1),
        )
        tagged2 = tagger.tag_investigation(canonical2)
        self.assertEqual(tagged2.medical_findings[0].tags, ())

    def test_positive_injury_tags_properly(self):
        vocab = {"injury.documented", "injury.bodily_pain", "injury.grievous"}
        tagger = DeterministicTagger(vocab)

        canonical = CanonicalInvestigation(
            case_metadata=CanonicalCaseMetadata(case_id=uuid4()),
            medical_findings=(
                make_fact("Lacerated wound on left forearm with severe bodily pain and bone fracture."),
            ),
            confidence_summary=ConfidenceSummary(fact_count=1),
        )
        tagged = tagger.tag_investigation(canonical)
        tags = set(tagged.medical_findings[0].tags)
        self.assertIn("injury.documented", tags)
        self.assertIn("injury.bodily_pain", tags)
        self.assertIn("injury.grievous", tags)

    def test_vehicle_and_accident_tagging(self):
        vocab = {"vehicle.involved", "accident.occurred", "driving.on_public_way"}
        tagger = DeterministicTagger(vocab)

        event = CanonicalTimelineEvent(
            event_id=uuid4(),
            description=make_fact("Collision occurred on public way near junction"),
        )
        veh = CanonicalVehicle(id=uuid4(), registration_number=make_fact("KA01AB1234"))
        canonical = CanonicalInvestigation(
            case_metadata=CanonicalCaseMetadata(case_id=uuid4()),
            timeline=(event,),
            vehicles=(veh,),
            confidence_summary=ConfidenceSummary(fact_count=2),
        )
        tagged = tagger.tag_investigation(canonical)
        self.assertIn("vehicle.involved", tagged.vehicles[0].registration_number.tags)
        self.assertIn("accident.occurred", tagged.timeline[0].description.tags)
        self.assertIn("driving.on_public_way", tagged.timeline[0].description.tags)

    def test_prose_tagger_quote_verification(self):
        vocab = {"accused.act.physical", "accused.act.weapon_use", "threat.communicated"}
        doc_id = uuid4()
        ocr_result = OCRResult(
            document_id=doc_id,
            pages=(OCRPage(page_number=1, text="The accused hit the victim with a heavy stick and threatened him.", confidence=0.9),),
            raw_text="The accused hit the victim with a heavy stick and threatened him.",
            confidence=0.9,
            metadata=OCRMetadata(provider="test", model="test", input_mime_type="application/pdf", processing_time_ms=1),
        )

        client = MockProseClient([
            # Valid verbatim quote
            {"document_id": str(doc_id), "tag": "accused.act.physical", "verbatim_quote": "hit the victim"},
            # Hallucinated quote not in text
            {"document_id": str(doc_id), "tag": "threat.communicated", "verbatim_quote": "I will kill your entire family tomorrow"},
            # Tag not in vocabulary
            {"document_id": str(doc_id), "tag": "unknown.custom_tag", "verbatim_quote": "heavy stick"},
        ])

        event = CanonicalTimelineEvent(
            event_id=uuid4(),
            description=make_fact("Witness says accused assaulted victim", doc_id=doc_id),
        )
        canonical = CanonicalInvestigation(
            case_metadata=CanonicalCaseMetadata(case_id=uuid4()),
            timeline=(event,),
            confidence_summary=ConfidenceSummary(fact_count=1),
        )

        prose_tagger = ProseTagger(client, vocab)
        tagged = prose_tagger.tag_investigation(canonical, {str(doc_id): ocr_result})

        event_tags = set(tagged.timeline[0].description.tags)
        self.assertIn("accused.act.physical", event_tags)
        self.assertNotIn("threat.communicated", event_tags)
        self.assertNotIn("unknown.custom_tag", event_tags)

    def test_fact_tagging_stage_writes_artifact(self):
        with TemporaryDirectory() as directory:
            storage_root = Path(directory)
            stage = FactTaggingStage(storage_root)
            case_id = uuid4()
            canonical = CanonicalInvestigation(
                case_metadata=CanonicalCaseMetadata(case_id=case_id),
                medical_findings=(make_fact("Documented injury with laceration"),),
                confidence_summary=ConfidenceSummary(fact_count=1),
            )
            wf_context = WorkflowContext(
                case_id=case_id,
                canonical_investigation=canonical,
                execution_state=WorkflowState(case_id=case_id),
            )
            updated = stage.execute(wf_context)
            self.assertTrue(any(a.name == "fact_tags" for a in updated.generated_artifacts))
            fact_tags_file = storage_root / f"CASE_{case_id.hex}" / "processed" / "legal" / "fact_tags.json"
            self.assertTrue(fact_tags_file.is_file())


if __name__ == "__main__":
    main()
