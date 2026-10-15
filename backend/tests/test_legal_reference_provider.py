from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from uuid import uuid4

from src.context.case_context import CaseContext
from src.domain.common import SourceReference
from src.extraction.ocr_client import OCRClient
from src.knowledge_graph.graph_models import GraphProvenance
from src.legal.evidence_mapper import EvidenceMapper
from src.legal.legal_findings import EvidenceStrength, LegalFinding, LegalFindingStatus, LegalFindings
from src.legal.legal_reasoner import LegalReasoner, LegalReasoningClient
from src.legal.legal_rules import LegalReferenceConfigurationError, LocalLegalReferenceProvider
from src.normalization.canonical_models import CanonicalFact, CanonicalTimelineEvent
from src.parsers.base_parser import ParserClient
from src.validation.validation_models import ValidationDisposition
from src.workflow.production import create_production_registry


DATASET_PATH = Path(__file__).parents[1] / "references" / "legal" / "bns_sections.json"
DATASET_VERSION = "bns-2023-2024-07-01"


def fact(value: str, tags: tuple[str, ...] = ()) -> CanonicalFact:
    document_id = uuid4()
    provenance = GraphProvenance(
        document_id=document_id,
        confidence=0.8,
        parser_name="fixture",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_reference=SourceReference(document_id=document_id),
    )
    return CanonicalFact(
        value=value,
        source_document_ids=(document_id,),
        references=(provenance,),
        source_path="fixture.hurt",
        confidence=0.8,
        extraction_method="fixture",
        timestamp=provenance.timestamp,
        tags=tags,
    )


def context(
    disposition: ValidationDisposition = ValidationDisposition.DRAFT_ALLOWED,
    offence_date: date = date(2024, 8, 1),
) -> CaseContext:
    doc_id = uuid4()
    event_timestamp = CanonicalFact(
        value=datetime(offence_date.year, offence_date.month, offence_date.day, 10, 0, tzinfo=timezone.utc),
        source_document_ids=(doc_id,),
        references=(GraphProvenance(document_id=doc_id, confidence=0.9, parser_name="fixture", timestamp=datetime.now(timezone.utc), source_reference=SourceReference(document_id=doc_id)),),
        source_path="fir.occurrence_datetime",
        confidence=0.9,
        extraction_method="fixture",
        timestamp=datetime.now(timezone.utc),
    )
    timeline_event = CanonicalTimelineEvent(
        event_id=uuid4(),
        timestamp=event_timestamp,
        description=fact("Incident occurrence", tags=("driving.on_public_way",)),
    )
    return CaseContext(
        case_id=uuid4(),
        fir_details=(event_timestamp,),
        occurrence_details=(timeline_event,),
        medical_findings=(fact("Documented injury with bodily pain", tags=("injury.documented", "injury.bodily_pain")),),
        validation_disposition=disposition.value,
    )


class QueueClient(LegalReasoningClient):
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def generate_json(self, prompt):
        return self.payloads.pop(0)


class NoopOCRClient(OCRClient):
    def extract(self, document, source_path):
        raise AssertionError("not invoked during registry construction")


class NoopParserClient(ParserClient):
    def generate_json(self, prompt):
        raise AssertionError("not invoked during registry construction")


class LegalReferenceProviderTests(TestCase):
    def test_versioned_dataset_loads_and_looks_up_known_section(self):
        provider = LocalLegalReferenceProvider.load(DATASET_PATH, DATASET_VERSION, allow_draft=True)
        section = provider.lookup("115")
        self.assertEqual(provider.dataset.version, DATASET_VERSION)
        self.assertIsNotNone(section)
        self.assertEqual(section.offence_name, "Voluntarily causing hurt")
        self.assertEqual(section.section_number, "115")
        self.assertEqual(section.sub_section, "2")
        self.assertEqual(section.key, "BNS:115(2)")
        self.assertEqual(section.version, DATASET_VERSION)
        self.assertEqual(section.source.publisher, "India Code")

        # Lookup by exact key
        key_section = provider.lookup("BNS:115(2)")
        self.assertEqual(key_section, section)

    def test_verified_only_gate_loads_zero_records_in_production_mode(self):
        provider = LocalLegalReferenceProvider.load(DATASET_PATH, DATASET_VERSION, allow_draft=False)
        self.assertEqual(len(provider.dataset.references), 0)
        self.assertEqual(len(provider.all_references), 30)

    def test_loader_rejects_unknown_fact_tag(self):
        with TemporaryDirectory() as directory:
            payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
            payload["references"][0]["elements"][0]["fact_tags"].append("unknown.nonexistent_tag")
            path = Path(directory) / "invalid_tag.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(LegalReferenceConfigurationError):
                LocalLegalReferenceProvider.load(path, DATASET_VERSION, allow_draft=True)

    def test_loader_rejects_unknown_relation_target(self):
        with TemporaryDirectory() as directory:
            payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
            payload["references"][0]["relations"].append({"key": "BNS:9999", "relation": "defines"})
            path = Path(directory) / "invalid_rel.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(LegalReferenceConfigurationError):
                LocalLegalReferenceProvider.load(path, DATASET_VERSION, allow_draft=True)

    def test_loader_rejects_missing_required_element(self):
        with TemporaryDirectory() as directory:
            payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
            payload["references"][0]["required_elements"].append("ghost_element")
            path = Path(directory) / "invalid_req.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(LegalReferenceConfigurationError):
                LocalLegalReferenceProvider.load(path, DATASET_VERSION, allow_draft=True)

    def test_loader_rejects_non_officer_element_without_tags(self):
        with TemporaryDirectory() as directory:
            payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
            payload["references"][0]["elements"][0]["fact_tags"] = []
            payload["references"][0]["elements"][0]["officer_judgment"] = False
            path = Path(directory) / "no_tags.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(LegalReferenceConfigurationError):
                LocalLegalReferenceProvider.load(path, DATASET_VERSION, allow_draft=True)

    def test_unknown_section_lookup_returns_none(self):
        provider = LocalLegalReferenceProvider.load(DATASET_PATH, DATASET_VERSION, allow_draft=True)
        self.assertIsNone(provider.lookup("9999"))

    def test_missing_or_mismatched_configuration_fails_safely(self):
        with self.assertRaises(LegalReferenceConfigurationError):
            LocalLegalReferenceProvider.load(None, DATASET_VERSION)
        with self.assertRaises(LegalReferenceConfigurationError):
            LocalLegalReferenceProvider.load(DATASET_PATH, "wrong-version")

    def test_invalid_dataset_version_metadata_is_rejected(self):
        with TemporaryDirectory() as directory:
            payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
            payload["references"][0]["version"] = "different-version"
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(LegalReferenceConfigurationError):
                LocalLegalReferenceProvider.load(path, DATASET_VERSION, allow_draft=True)

    def test_production_registry_loads_configured_provider_and_rejects_missing_configuration(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(LegalReferenceConfigurationError):
                create_production_registry(Path(directory))
            registry = create_production_registry(
                Path(directory),
                ocr_client=NoopOCRClient(),
                parser_client=NoopParserClient(),
                legal_reference_path=DATASET_PATH,
                legal_reference_version=DATASET_VERSION,
                allow_draft_legal=True,
            )
            legal_stage = next(stage for stage in registry.stages if stage.name == "legal_reasoning")
            self.assertIsInstance(legal_stage.reasoner.reference_provider, LocalLegalReferenceProvider)

    def test_configured_reference_can_produce_supported_finding_with_evidence(self):
        provider = LocalLegalReferenceProvider.load(DATASET_PATH, DATASET_VERSION, allow_draft=True)
        ctx = context()
        # Provide all required element tags for BNS:115(2)
        ctx = ctx.model_copy(update={
            "medical_findings": (
                fact("Documented injury with bodily pain", tags=("injury.documented", "injury.bodily_pain")),
                fact("Medical opinion links act to injury", tags=("link.act_to_injury",)),
            ),
            "occurrence_details": (
                CanonicalTimelineEvent(
                    event_id=uuid4(),
                    timestamp=ctx.occurrence_details[0].timestamp,
                    description=fact("Accused physically struck victim", tags=("accused.identified", "accused.act.physical", "intent.indicator.knowledge_of_risk")),
                ),
            ),
        })
        result = LegalReasoner(provider).reason(ctx)
        self.assertTrue(result.findings)
        finding_115 = next((f for f in result.findings if "115" in f.proposed_section), None)
        self.assertIsNotNone(finding_115)
        self.assertEqual(finding_115.status, LegalFindingStatus.SUPPORTED)
        self.assertEqual(finding_115.section_key, "BNS:115(2)")
        self.assertTrue(finding_115.supporting_evidence)

    def test_llm_unknown_section_and_missing_evidence_become_review_required(self):
        provider = LocalLegalReferenceProvider.load(DATASET_PATH, DATASET_VERSION, allow_draft=True)
        ctx = context()
        mapping = EvidenceMapper().available(ctx)[0]
        unknown = LegalFindings(
            findings=(
                LegalFinding(
                    legal_reference_id=uuid4(),
                    section_key="BNS:9999",
                    law_code="BNS",
                    offence="Unknown",
                    proposed_section="9999",
                    description="Unknown",
                    supporting_evidence=(mapping,),
                    evidence_strength=EvidenceStrength.LOW,
                    confidence=.1,
                    status=LegalFindingStatus.REVIEW_REQUIRED,
                    review_required=True,
                    source_references=mapping.source_references,
                ),
            ),
            review_required=True,
            validation_disposition=ValidationDisposition.DRAFT_ALLOWED.value,
            retry_count=0,
        ).model_dump(mode="json")
        missing_evidence = json.loads(json.dumps(unknown))
        ref_115 = provider.lookup("115")
        missing_evidence["findings"][0]["legal_reference_id"] = str(ref_115.section_id)
        missing_evidence["findings"][0]["proposed_section"] = "115"
        missing_evidence["findings"][0]["section_key"] = ref_115.key
        missing_evidence["findings"][0]["supporting_evidence"] = []
        result = LegalReasoner(provider, QueueClient([unknown, missing_evidence])).reason(ctx)
        self.assertFalse(result.findings)
        self.assertTrue(result.review_required)
        self.assertEqual(result.retry_count, 2)

    def test_final_blocked_never_returns_legal_findings(self):
        provider = LocalLegalReferenceProvider.load(DATASET_PATH, DATASET_VERSION, allow_draft=True)
        result = LegalReasoner(provider).reason(context(ValidationDisposition.FINAL_BLOCKED))
        self.assertFalse(result.findings)
        self.assertTrue(result.review_required)


if __name__ == "__main__":
    main()
