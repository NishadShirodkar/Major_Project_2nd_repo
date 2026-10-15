"""Unit tests for statutory date-gating logic (BNS vs IPC vs review required)."""

from datetime import date, datetime, timezone
from unittest import TestCase, main
from uuid import uuid4

from src.context.case_context import CaseContext
from src.domain.common import SourceReference
from src.knowledge_graph.graph_models import GraphProvenance
from src.legal.date_gate import extract_offence_date, filter_references_by_date, select_law
from src.legal.legal_rules import LegalReference, LegalReferenceSource, LegalJurisdiction
from src.normalization.canonical_models import CanonicalFact, CanonicalTimelineEvent


def make_ref(section_number: str, effective_from: date, effective_to: date | None = None) -> LegalReference:
    return LegalReference(
        section_id=uuid4(),
        key=f"BNS:{section_number}",
        law_code="BNS",
        section_number=section_number,
        offence_name=f"Offence {section_number}",
        description=f"Desc {section_number}",
        jurisdiction=LegalJurisdiction.INDIA,
        effective_from=effective_from,
        effective_to=effective_to,
        source=LegalReferenceSource(publisher="India Code", citation="Citation", uri="https://example.com"),
        version="bns-2023-2024-07-01",
        source_reference=SourceReference(document_id=uuid4()),
    )


class DateGateTests(TestCase):
    def test_offence_date_selection_rules(self):
        # 1. 30 June 2024 -> IPC
        self.assertEqual(select_law(date(2024, 6, 30)), "IPC")
        self.assertEqual(select_law(date(2020, 1, 1)), "IPC")

        # 2. 1 July 2024 -> BNS
        self.assertEqual(select_law(date(2024, 7, 1)), "BNS")
        self.assertEqual(select_law(date(2026, 1, 1)), "BNS")

        # 3. None -> None (requires officer review)
        self.assertIsNone(select_law(None))

    def test_filter_references_by_date(self):
        ref_old = make_ref("old", date(1860, 1, 1), date(2024, 6, 30))
        ref_bns = make_ref("bns", date(2024, 7, 1), None)
        refs = (ref_old, ref_bns)

        # Offence on 2024-06-15: only old applies
        res_old = filter_references_by_date(refs, date(2024, 6, 15))
        self.assertEqual(tuple(r.section_number for r in res_old), ("old",))

        # Offence on 2024-07-01: only bns applies
        res_new = filter_references_by_date(refs, date(2024, 7, 1))
        self.assertEqual(tuple(r.section_number for r in res_new), ("bns",))

        # Offence date None: empty references
        res_none = filter_references_by_date(refs, None)
        self.assertEqual(res_none, ())

    def test_extract_offence_date_from_context(self):
        doc_id = uuid4()
        timestamp_fact = CanonicalFact(
            value="2024-08-15T14:30:00",
            source_document_ids=(doc_id,),
            references=(GraphProvenance(document_id=doc_id, confidence=0.9, parser_name="fixture", timestamp=datetime.now(timezone.utc), source_reference=SourceReference(document_id=doc_id)),),
            source_path="fir.occurrence_datetime",
            confidence=0.9,
            extraction_method="fixture",
            timestamp=datetime.now(timezone.utc),
        )
        ctx = CaseContext(case_id=uuid4(), fir_details=(timestamp_fact,), validation_disposition="draft_allowed")
        extracted_date, ambiguous = extract_offence_date(ctx)
        self.assertEqual(extracted_date, date(2024, 8, 15))
        self.assertFalse(ambiguous)

    def test_missing_offence_date_marks_ambiguous(self):
        ctx = CaseContext(case_id=uuid4(), validation_disposition="draft_allowed")
        extracted_date, ambiguous = extract_offence_date(ctx)
        self.assertIsNone(extracted_date)
        self.assertTrue(ambiguous)


if __name__ == "__main__":
    main()

