"""Deterministic filename and media-type classification; no AI is used here."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..domain.common import ConfidenceLevel
from ..domain.documents import DocumentType


class ClassificationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_type: DocumentType
    confidence: ConfidenceLevel
    reason: str


class DeterministicDocumentClassifier:
    """Classifies known evidence categories using auditable filename keywords."""

    _KEYWORDS: tuple[tuple[DocumentType, tuple[str, ...]], ...] = (
        (DocumentType.POSTMORTEM_REPORT, ("postmortem", "post mortem", "autopsy")),
        (DocumentType.MEDICAL_REPORT, ("medical", "mlc", "injury", "hospital")),
        (DocumentType.FSL_REPORT, ("fsl", "forensic", "laboratory")),
        (DocumentType.WITNESS_STATEMENT, ("witness", "statement_161", "161 statement", "statement")),
        (DocumentType.CASE_DIARY, ("case diary", "case_diary", "diary")),
        (DocumentType.SEIZURE_MEMO, ("seizure", "recovery memo")),
        (DocumentType.ARREST_MEMO, ("arrest", "personal search")),
        (DocumentType.SPOT_PANCHNAMA, ("panchanama", "panchnama", "spot memo", "scene")),
        (DocumentType.VEHICLE_INSPECTION, ("vehicle inspection", "mechanical inspection", "vir")),
        (DocumentType.SITE_PLAN, ("site plan", "site_plan", "rough sketch")),
        (DocumentType.COMPLAINT, ("complaint", "application")),
        (DocumentType.FIR, ("fir", "first information report")),
        (DocumentType.CCTV_IMAGE, ("cctv", "camera", "surveillance")),
    )

    _CONTENT_MARKERS: tuple[tuple[DocumentType, tuple[str, ...]], ...] = (
        (DocumentType.POSTMORTEM_REPORT, ("post-mortem examination", "postmortem examination", "post mortem report", "autopsy report", "cause of death")),
        (DocumentType.MEDICAL_REPORT, ("medico-legal", "medico legal", "mlc no", "casualty department", "nature of injury", "examination of injured", "patient name")),
        (DocumentType.FSL_REPORT, ("forensic science laboratory", "ballistics division", "chemical examination report", "biology division", "fsl report")),
        (DocumentType.WITNESS_STATEMENT, ("statement under section 161", "statement u/s 161", "161 cr.p.c", "statement of witness", "witness statement", "statement of accused", "accused statement")),
        (DocumentType.CASE_DIARY, ("case diary", "special diary", "case diary under section 172")),
        (DocumentType.SEIZURE_MEMO, ("seizure memo", "recovery memo", "panchnama of seizure", "memo of recovery", "inventory of seized")),
        (DocumentType.ARREST_MEMO, ("memo of arrest", "arrest memo", "arrested person details", "grounds of arrest")),
        (DocumentType.SPOT_PANCHNAMA, ("spot panchnama", "scene of occurrence panchnama", "panchanama of the scene", "spot inspection memo")),
        (DocumentType.VEHICLE_INSPECTION, ("vehicle inspection report", "mechanical inspection report", "inspection of motor vehicle", "mvi report")),
        (DocumentType.SITE_PLAN, ("site plan", "rough sketch of spot", "scale plan of scene", "rough site plan")),
        (DocumentType.COMPLAINT, ("to the station house officer", "written complaint", "complaint subject", "complaint against", "prayer:")),
        (DocumentType.FIR, ("first information report", "integrated investigation form", "form i.f. 1", "form if-1", "form if 1", "fir no", "f.i.r. no")),
        (DocumentType.CCTV_IMAGE, ("cctv analysis report", "cctv report", "camera id", "cctv footage", "cctv metadata")),
    )

    def classify_content(self, text: str) -> ClassificationResult | None:
        """Classify a document by inspecting unambiguous header markers in raw text."""
        if not text or not text.strip():
            return None
        header_text = text[:1500].lower()
        normalized_header = re.sub(r"[\s_-]+", " ", header_text)
        for document_type, markers in self._CONTENT_MARKERS:
            for marker in markers:
                if marker in normalized_header:
                    return ClassificationResult(
                        document_type=document_type,
                        confidence=ConfidenceLevel.HIGH,
                        reason=f"Matched unambiguous document content marker: '{marker}'.",
                    )
        return None

    def classify(self, filename: str, media_type: str | None, content: str | None = None) -> ClassificationResult:
        normalized_name = re.sub(r"[_-]+", " ", Path(filename).stem.lower())
        for document_type, keywords in self._KEYWORDS:
            if any(keyword in normalized_name for keyword in keywords):
                return ClassificationResult(
                    document_type=document_type,
                    confidence=ConfidenceLevel.HIGH,
                    reason="Matched deterministic filename keyword.",
                )

        if content:
            content_result = self.classify_content(content)
            if content_result:
                return content_result

        if media_type and media_type.startswith("video/"):
            return ClassificationResult(
                document_type=DocumentType.CCTV_VIDEO,
                confidence=ConfidenceLevel.MEDIUM,
                reason="Classified from video MIME type.",
            )
        if media_type and media_type.startswith("image/"):
            return ClassificationResult(
                document_type=DocumentType.CCTV_IMAGE,
                confidence=ConfidenceLevel.LOW,
                reason="Classified from image MIME type; officer review required.",
            )
        return ClassificationResult(
            document_type=DocumentType.OTHER,
            confidence=ConfidenceLevel.LOW,
            reason="No deterministic classification rule matched; officer review required.",
        )
