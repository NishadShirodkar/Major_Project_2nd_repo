"""Deterministic mock OCR and Parser clients for offline, reproducible execution and CLI runs."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from ..domain.documents import DocumentType, SourceDocument
from ..parsers.base_parser import ParserClient
from .ocr_client import OCRClient
from .ocr_result import OCRMetadata, OCRPage, OCRResult


class MockOCRClient(OCRClient):
    """Deterministic offline OCR provider returning realistic mock transcriptions."""

    supported_mime_types = frozenset({
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "text/plain",
        "application/octet-stream",
    })

    def supports(self, document: SourceDocument) -> bool:
        return True

    def extract(self, document: SourceDocument, source_path: Path) -> OCRResult:
        # If the file actually exists on disk and contains digital text, extract REAL content!
        if source_path.is_file():
            if document.media_type == "application/pdf" or str(source_path).endswith(".pdf"):
                from .pdf_extractor import extract_digital_pdf_pages
                digital_pages = extract_digital_pdf_pages(source_path)
                if digital_pages and sum(len(p.strip()) for p in digital_pages) >= 50:
                    pages = tuple(
                        OCRPage(page_number=idx, text=page_text, confidence=0.99)
                        for idx, page_text in enumerate(digital_pages, 1)
                    )
                    return OCRResult(
                        document_id=document.id,
                        pages=pages,
                        raw_text="\n\n".join(page.text for page in pages),
                        confidence=0.99,
                        metadata=OCRMetadata(
                            provider="mock_ocr",
                            model="digital_pdf_reader",
                            input_mime_type=document.media_type or "application/pdf",
                            processing_time_ms=5.0,
                            token_usage=sum(len(p.split()) for p in digital_pages),
                            estimated_cost=0.0,
                        ),
                    )
            elif source_path.suffix.lower() in (".txt", ".json", ".csv"):
                try:
                    text = source_path.read_text(encoding="utf-8")
                    if text.strip():
                        page = OCRPage(page_number=1, text=text, confidence=0.99)
                        return OCRResult(
                            document_id=document.id,
                            pages=(page,),
                            raw_text=text,
                            confidence=0.99,
                            metadata=OCRMetadata(
                                provider="mock_ocr",
                                model="local_file_reader",
                                input_mime_type="text/plain",
                                processing_time_ms=1.0,
                                token_usage=len(text.split()),
                                estimated_cost=0.0,
                            ),
                        )
                except Exception:
                    pass

        # Fallback to deterministic mock text for synthetic test fixtures
        filename = (document.original_filename or "").lower()
        text = self._generate_mock_text(filename, document.detected_type)

        page = OCRPage(page_number=1, text=text, confidence=0.95)
        metadata = OCRMetadata(
            provider="mock_ocr",
            model="deterministic_mock",
            input_mime_type=document.media_type or "application/pdf",
            processing_time_ms=5.0,
            token_usage=len(text.split()),
            estimated_cost=0.0,
        )
        return OCRResult(
            document_id=document.id,
            pages=(page,),
            raw_text=text,
            confidence=0.95,
            metadata=metadata,
        )

    def _generate_mock_text(self, filename: str, detected_type: DocumentType) -> str:
        if "fir" in filename or detected_type == DocumentType.FIR:
            return (
                "FIRST INFORMATION REPORT (Under Section 173 BNSS / 154 CrPC)\n"
                "FIR No: 42/2026 Date: 2026-01-02\n"
                "Police Station: Central PS, District: Central, State: NCT\n"
                "Complainant: Asha Devi\n"
                "Accused: Raj Verma\n"
                "Victim: Sameer Khan\n"
                "Date and Time of Occurrence: 2026-01-01T10:00:00\n"
                "Place of Occurrence: Market Road, Central\n"
                "Vehicle Registration: KA01AB1234\n"
                "Acts & Sections: Section 115 BNS (Voluntarily causing hurt)\n"
                "Narrative: Complainant Asha Devi reported that on 2026-01-01 at 10:00 hrs at Market Road, "
                "accused Raj Verma assaulted victim Sameer Khan with a blunt object causing bodily hurt. "
                "Vehicle KA01AB1234 was used by the accused to flee the spot."
            )
        if "complaint" in filename or detected_type == DocumentType.COMPLAINT:
            return (
                "WRITTEN COMPLAINT\n"
                "Date: 2026-01-01\n"
                "To: The Station House Officer, Central PS\n"
                "From: Asha Devi, R/o Market Road\n"
                "Against: Raj Verma\n"
                "Subject: Complaint regarding physical assault on Sameer Khan.\n"
                "Details: Today at 10:00 AM at Market Road, Raj Verma physically attacked Sameer Khan "
                "causing him severe bodily hurt. The accused fled in car KA01AB1234. Please register FIR."
            )
        if "witness" in filename or detected_type == DocumentType.WITNESS_STATEMENT:
            return (
                "STATEMENT OF WITNESS UNDER SECTION 180 BNSS / 161 CrPC\n"
                "Date: 2026-01-02\n"
                "Witness Name: Ravi Kumar, Age: 34, Address: Market Road\n"
                "Recorded By: Officer Rao, Central PS\n"
                "Statement: I state that on 2026-01-01 around 10:00 AM, I was present near the tea shop on Market Road. "
                "I witnessed Raj Verma arguing with Sameer Khan and then assaulting him with fists and a stick, causing hurt."
            )
        if "medical" in filename or detected_type == DocumentType.MEDICAL_REPORT:
            return (
                "MEDICO-LEGAL EXAMINATION REPORT (MLC)\n"
                "MLC Report No: MLC-1 Date: 2026-01-02\n"
                "Hospital: Civil Hospital, Central\n"
                "Examining Doctor: Dr Sen, MD (Forensic Medicine)\n"
                "Patient Name: Asha Devi / Sameer Khan\n"
                "Observations: 1. Contusion over left forearm (3cm x 2cm). 2. Abrasion over left shoulder. "
                "Nature of injury: Simple hurt caused by blunt force weapon."
            )
        if "postmortem" in filename or detected_type == DocumentType.POSTMORTEM_REPORT:
            return (
                "POST-MORTEM EXAMINATION REPORT\n"
                "PM No: PM-1 Date: 2026-01-03\n"
                "Mortuary: Civil Hospital Mortuary\n"
                "Deceased Name: Sameer Khan\n"
                "Doctor: Dr Sen\n"
                "Findings: Laceration on occipital region. Death due to cranio-cerebral damage."
            )
        if "fsl" in filename or detected_type == DocumentType.FSL_REPORT:
            return (
                "FORENSIC SCIENCE LABORATORY REPORT\n"
                "FSL Report No: FSL-1 Date: 2026-01-05\n"
                "Laboratory: State Forensic Science Laboratory\n"
                "Examined Items: 1. CCTV DVR exhibit mark E1, 2. Blunt wooden weapon exhibit mark W1.\n"
                "Findings: CCTV DVR footage is intact and authentic without tampering. Blunt wooden weapon shows matching blood group."
            )
        if "seizure" in filename or detected_type == DocumentType.SEIZURE_MEMO:
            return (
                "SEIZURE MEMO / PANCHNAMA (Section 105 BNSS / 102 CrPC)\n"
                "Memo No: SZ-1 Date & Time: 2026-01-02T14:00:00\n"
                "Location of Seizure: Market Road, Central\n"
                "Prepared by: Officer Rao\n"
                "Seized Items: CCTV DVR system recovered from shop premises, exhibit mark E1."
            )
        if "vehicle" in filename or detected_type == DocumentType.VEHICLE_INSPECTION:
            return (
                "MOTOR VEHICLE INSPECTION REPORT\n"
                "Report No: VI-1 Date: 2026-01-03\n"
                "Vehicle Registration: KA01AB1234\n"
                "Inspecting Officer: Officer Rao, Central PS\n"
                "Observations: Front left bumper scratched, mechanical condition fit."
            )
        if "site" in filename or detected_type == DocumentType.SITE_PLAN:
            return (
                "SITE PLAN / MAP OF CRIME SCENE\n"
                "Plan No: SP-1 Date: 2026-01-02\n"
                "Location: Market Road, Near Tea Stall, Central\n"
                "Prepared by: Officer Rao\n"
                "Annotations: Point A indicates place of assault; Point B indicates parking of KA01AB1234."
            )
        if "panchnama" in filename or "spot" in filename or detected_type == DocumentType.SPOT_PANCHNAMA:
            return (
                "SPOT PANCHNAMA\n"
                "Memo No: SP-01 Date: 2026-01-02T11:00:00\n"
                "Location: Market Road, Central\n"
                "Witnesses: Ramesh Patel, Suresh Sharma\n"
                "Observations: Broken glass and blood marks found at the spot."
            )
        if "arrest" in filename or detected_type == DocumentType.ARREST_MEMO:
            return (
                "ARREST MEMO\n"
                "Memo No: AR-1 Date: 2026-01-02T16:00:00\n"
                "Arrested Person: Raj Verma\n"
                "Arresting Officer: Officer Rao\n"
                "Location: Market Road, Central."
            )
        if "diary" in filename or detected_type == DocumentType.CASE_DIARY:
            return (
                "CASE DIARY ENTRY\n"
                "Diary No: CD-1 Date: 2026-01-02\n"
                "Officer: Officer Rao\n"
                "Entry: Visited scene of crime and recorded witness statements."
            )
        if "cctv" in filename or detected_type == DocumentType.CCTV_IMAGE:
            return (
                "CCTV METADATA REPORT\n"
                "Camera ID: CAM-01 Location: Market Road\n"
                "Recording Date & Time: 2026-01-01T10:00:00 Duration: 120s\n"
                "Metadata: High definition video recording showing vehicle KA01AB1234."
            )
        return f"GENERAL INVESTIGATION DOCUMENT: {filename}\nContains evidentiary notes for case investigation."


def _normalize_date_str(date_str: str | None) -> str:
    if not date_str:
        return "2024-01-01"
    s = date_str.strip()
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m_iso = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
    if m_iso:
        return f"{m_iso.group(1)}-{int(m_iso.group(2)):02d}-{int(m_iso.group(3)):02d}"
    return "2024-01-01"


class MockParserClient(ParserClient):
    """Deterministic offline parser provider generating validated JSON structures."""

    def _sanitize_entities(self, payload: dict[str, Any], ocr_text: str) -> dict[str, Any]:
        norm_ocr = re.sub(r"[^a-z0-9]", "", ocr_text.casefold())
        if not norm_ocr:
            return payload
        cleaned = dict(payload)
        for key in ("accused_names", "victim_names", "vehicle_registrations", "person_complained_against_names"):
            if key in cleaned and isinstance(cleaned[key], (list, tuple)):
                cleaned[key] = [x for x in cleaned[key] if isinstance(x, str) and re.sub(r"[^a-z0-9]", "", x.casefold()) in norm_ocr]
        for key in ("complainant_name", "patient_name", "deceased_name", "witness_name"):
            if key in cleaned and isinstance(cleaned[key], str):
                if re.sub(r"[^a-z0-9]", "", cleaned[key].casefold()) not in norm_ocr:
                    cleaned[key] = None
        return cleaned

    def generate_json(self, prompt: str) -> dict[str, Any]:
        prompt_cf = prompt.casefold()
        split_idx = prompt.find("OCR transcription (preserve its meaning; do not add information):")
        ocr_text = prompt[split_idx:] if split_idx != -1 else prompt

        # Separate true copy / digital generation banner from substantive document body
        body_text = ocr_text
        if "--------------------------------------------------------------------------------" in ocr_text:
            body_text = ocr_text.split("--------------------------------------------------------------------------------")[-1]

        # 1. FIR PARSER
        if '"fir"' in prompt_cf or 'reported_sections' in prompt_cf:
            fir_m = re.search(r'(?:Fir Number|FIR No\.?|Crime No\.?|Case No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', body_text, re.I) or re.search(r'(?:Fir Number|FIR No\.?|Crime No\.?|Case No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', ocr_text, re.I)
            date_m = re.search(r'(?:Date Of Fir|Registration Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I) or re.search(r'(?:Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)
            norm_date = _normalize_date_str(date_m.group(1) if date_m else None)

            ps_m = (
                re.search(r'POLICE STATION\s*\n\s*Name:\s*([^\r\n]+)', body_text, re.I) or
                re.search(r'(?:Police\s*Station|PS|Thana)(?:\s*Name)?[:\s\r\n]+([^\r\n]+)', body_text, re.I) or
                re.search(r'POLICE STATION\s*\n\s*Name:\s*([^\r\n]+)', ocr_text, re.I) or
                re.search(r'(?:Police\s*Station|PS|Thana)(?:\s*Name)?[:\s\r\n]+([^\r\n]+)', ocr_text, re.I)
            )
            ps_val = "Unknown Police Station"
            if ps_m:
                ps_val = re.split(r'\s*(?:Address|District|State|Phone|Beat|FIR|Complainant|ACCUSED|VICTIM|Date|\n)', ps_m.group(1))[0].strip().strip(",-")

            acc_m = re.search(r'ACCUSED DETAILS[\s\S]*?Name:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'(?:Accused(?:\s*Details)?(?:\s*Name)?|Person\s*Accused)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            acc_list = []
            if acc_m:
                val = re.split(r'\s*(?:Father|Age|Address|Nationality|Occupation|riding|\n)', acc_m.group(1))[0].strip().strip(",-")
                if val and len(val) > 1 and val.casefold() not in ("none", "nil", "unknown", "n/a"):
                    acc_list.append(val)

            vic_m = re.search(r'VICTIM DETAILS[\s\S]*?Name:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'(?:Victim(?:\s*Details)?(?:\s*Name)?|Injured\s*Person)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            vic_list = []
            if vic_m:
                val = re.split(r'\s*(?:Father|Age|Occupation|Address|Injury|Hospital|Status|riding|\n)', vic_m.group(1))[0].strip().strip(",-")
                if val and len(val) > 1 and val.casefold() not in ("none", "nil", "unknown", "n/a"):
                    vic_list.append(val)

            comp_m = re.search(r'COMPLAINANT[\s\S]*?Name:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'(?:Complainant(?:\s*Details)?(?:\s*Name)?|Informant)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            comp_val = None
            if comp_m:
                val = re.split(r'\s*(?:Father|Husband|W/o|S/o|D/o|Age|Occupation|Address|R/o|\n)', comp_m.group(1))[0].strip().strip(",-")
                if val and len(val) > 1 and val.casefold() not in ("none", "nil", "unknown", "n/a"):
                    comp_val = val

            loc_m = re.search(r'(?:Place Of Occurrence|Occurrence Location|Place|Location)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            loc_val = "Incident Location"
            if loc_m:
                loc_val = re.split(r'\s*(?:Distance|Direction|Beat|COMPLAINANT|VICTIM|ACCUSED|\n)', loc_m.group(1))[0].strip().strip(",-")

            vehicles = re.findall(r'\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4})\b', body_text) or re.findall(r'\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4})\b', ocr_text)
            clean_v = list(dict.fromkeys(v.replace(' ', '') for v in vehicles))

            sections = re.findall(r'(?:Section|Sec\.?)\s*(\d+[A-Z]?)', body_text, re.I) or re.findall(r'(?:Section|Sec\.?)\s*(\d+[A-Z]?)', ocr_text, re.I)
            clean_sec = list(dict.fromkeys(sections)) if sections else ["281"]

            court_m = re.search(r'FIR FORWARDED TO[\s\S]*?Item 1:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'Court[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            court_val = court_m.group(1).strip() if court_m else "Judicial Magistrate Court"

            time_m = re.search(r'(?:Time From|Time Of Fir|Time|at about)\s*[:\s\r\n]*(\d{1,2}[:.]\d{2})', body_text, re.I)
            time_str = "10:00:00"
            if time_m:
                t_parts = time_m.group(1).replace(".", ":").split(":")
                time_str = f"{int(t_parts[0]):02d}:{int(t_parts[1]):02d}:00"
            occ_dt = f"{norm_date}T{time_str}"

            brief_m = re.search(r'(?:Brief Facts|Narrative|Details)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            narrative = brief_m.group(1).strip() if brief_m else body_text[:300].strip()

            raw_dict = {
                "fir_number": fir_m.group(1).strip() if fir_m else "FIR-UNKNOWN",
                "crime_number": f"CR-{fir_m.group(1).strip() if fir_m else 'UNKNOWN'}",
                "registration_date": norm_date,
                "police_station": ps_val,
                "complainant_name": comp_val,
                "accused_names": acc_list,
                "victim_names": vic_list,
                "vehicle_registrations": clean_v,
                "occurrence_datetime": occ_dt,
                "occurrence_location": loc_val,
                "jurisdiction": ps_val,
                "court": court_val,
                "reported_sections": clean_sec,
                "narrative_text": narrative,
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 2. COMPLAINT PARSER
        if '"complaint"' in prompt_cf or 'complaint_text' in prompt_cf:
            date_m = re.search(r'(?:Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I) or re.search(r'(?:Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', ocr_text, re.I)
            comp_m = re.search(r'(?:From|Complainant Name|Complainant)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            comp_val = None
            if comp_m:
                val = re.split(r'\s*(?:R/o|Address|W/o|S/o|D/o|\n)', comp_m.group(1))[0].strip().strip(",-")
                if val and len(val) > 1:
                    comp_val = val

            acc_m = re.search(r'(?:Against|Accused|Person Complained Against)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            acc_list = []
            if acc_m:
                val = re.split(r'\s*(?:riding|driving|Address|\n)', acc_m.group(1))[0].strip().strip(",-")
                if val and len(val) > 1:
                    acc_list.append(val)

            vic_m = re.search(r'(?:Victim|assault on|hit by rashly driven|hit)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            vic_list = []
            if vic_m:
                val = re.split(r'\s*(?:riding|driving|at|causing|\n)', vic_m.group(1))[0].strip().strip(",-")
                if val and len(val) > 1 and val.casefold() not in ("me", "him", "her", "them", "the"):
                    vic_list.append(val)

            vehicles = re.findall(r'\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4})\b', body_text)
            clean_v = list(dict.fromkeys(v.replace(' ', '') for v in vehicles))

            addr_m = re.search(r'(?:R/o|Address)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            comp_addr = addr_m.group(1).strip() if addr_m else None

            raw_dict = {
                "complaint_date": _normalize_date_str(date_m.group(1) if date_m else None),
                "complainant_name": comp_val,
                "complainant_address": comp_addr,
                "person_complained_against_names": acc_list,
                "victim_names": vic_list,
                "vehicle_registrations": clean_v,
                "complaint_text": body_text[:400].strip(),
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 3. WITNESS STATEMENT PARSER
        if '"witnessstatement"' in prompt_cf or 'statement_text' in prompt_cf:
            date_m = re.search(r'(?:Date Of Recording|Date Of Statement)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I) or re.search(r'(?:Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)
            w_match = re.search(r'WITNESS DETAILS[\s\S]*?Name:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'(?:Witness Name|Statement Of|Witness)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            w_val = "Witness"
            if w_match:
                w_val = re.split(r'\s*(?:Age|Address|S/o|D/o|R/o|\n)', w_match.group(1))[0].strip().strip(",-")

            rec_m = re.search(r'(?:Recorded By|Officer)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            rec_val = "Investigating Officer"
            if rec_m:
                rec_val = re.split(r'\s*(?:PS|Police Station|Rank|\n)', rec_m.group(1))[0].strip().strip(",-")

            stmt_m = re.search(r'(?:Statement Text|Statement|Details)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            stmt_val = stmt_m.group(1).strip() if stmt_m else body_text[:300].strip()

            addr_m = re.search(r'Address[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            w_addr = addr_m.group(1).strip() if addr_m else None
            fn_m = re.search(r'Father(?:\s*Name)?[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            w_fn = fn_m.group(1).strip() if fn_m else None
            age_m = re.search(r'Age[:\s\r\n]+(\d+)', body_text, re.I)
            w_age = age_m.group(1).strip() if age_m else None
            occ_m = re.search(r'Occupation[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            w_occ = occ_m.group(1).strip() if occ_m else None
            contact_m = re.search(r'Contact[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            w_contact = contact_m.group(1).strip() if contact_m else None

            raw_dict = {
                "statement_date": _normalize_date_str(date_m.group(1) if date_m else None),
                "witness_name": w_val,
                "witness_address": w_addr,
                "recorded_by": rec_val,
                "statement_text": stmt_val,
                "father_name": w_fn,
                "age": w_age,
                "occupation": w_occ,
                "contact": w_contact,
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 4. MEDICAL REPORT PARSER
        if '"medicalreport"' in prompt_cf or 'patient_name' in prompt_cf:
            rep_m = re.search(r'(?:MLC No\.?|MLC Number|MLC Report No\.?|Report No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', body_text, re.I) or re.search(r'(?:MLC No\.?|MLC Number|MLC Report No\.?|Report No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', ocr_text, re.I)
            date_m = re.search(r'(?:Date Of Admission|Date Of Examination)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I) or re.search(r'(?:Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)
            pat_m = re.search(r'PATIENT DETAILS[\s\S]*?Name:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'(?:Patient Name|Name|Patient)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            pat_val = None
            if pat_m:
                val = re.split(r'\s*(?:Age|Sex|Hospital|Doctor|\n)', pat_m.group(1))[0].strip().strip(",-")
                if val and len(val) > 1:
                    pat_val = val

            doc_m = re.search(r'ATTENDING DOCTOR[\s\S]*?Name:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'(?:Examining Doctor|Doctor|Dr\.?)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            doc_val = doc_m.group(1).strip() if doc_m else "Examining Medical Officer"

            hosp_m = re.search(r'(?:Hospital)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            hosp_val = hosp_m.group(1).strip() if hosp_m else "Civil Hospital"

            obs: list[str] = []
            for inj in ("Compound fracture", "Fracture femur", "Clavicle fracture", "Contusion", "Abrasion", "Laceration", "Grievous injury", "Blunt chest trauma", "Bodily hurt", "Hurt"):
                if inj.casefold() in body_text.casefold():
                    obs.append(inj)
            if not obs:
                obs = ["Medical examination completed; injury assessment documented."]

            op_m = re.search(r'(?:Nature of injury|Opinion|Observations)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            op_val = op_m.group(1).strip() if op_m else "Medical examination conducted."

            age_m = re.search(r'Age[:\s\r\n]+(\d+)', body_text, re.I)
            pat_age = age_m.group(1).strip() if age_m else None
            sex_m = re.search(r'(?:Sex|Gender)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            pat_sex = sex_m.group(1).strip() if sex_m else None

            raw_dict = {
                "report_number": rep_m.group(1).strip() if rep_m else "MLC-01",
                "report_date": _normalize_date_str(date_m.group(1) if date_m else None),
                "patient_name": pat_val,
                "doctor_name": doc_val,
                "hospital_name": hosp_val,
                "observations": obs,
                "opinion_text": op_val,
                "age": pat_age,
                "gender": pat_sex,
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 5. POST-MORTEM PARSER
        if '"postmortemreport"' in prompt_cf or 'deceased_name' in prompt_cf:
            ocr_cf = ocr_text.casefold()
            is_na = "not applicable" in ocr_cf or "alive" in ocr_cf or "survived" in ocr_cf or "undergoing medical treatment" in ocr_cf or "undergoing treatment" in ocr_cf or "brought dead:\s*false" in ocr_cf
            if is_na:
                return {
                    "report_number": "PM-NA-01",
                    "examination_date": None,
                    "deceased_name": None,
                    "doctor_name": None,
                    "findings": [],
                    "opinion_text": "Victim is alive and undergoing medical treatment; post-mortem examination is not applicable.",
                    "status": "Not Applicable",
                    "is_applicable": False,
                    "confidence": 0.99,
                }

            dec_m = re.search(r'(?:Deceased Name|Deceased|Name)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            dec_val = None
            if dec_m:
                val = re.split(r'\s*(?:Age|Doctor|Date|\n)', dec_m.group(1))[0].strip().strip(",-")
                if val and len(val) > 1:
                    dec_val = val

            rep_m = re.search(r'(?:PM No\.?|Report No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', body_text, re.I)
            date_m = re.search(r'(?:Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)

            raw_dict = {
                "report_number": rep_m.group(1).strip() if rep_m else "PM-1",
                "examination_date": _normalize_date_str(date_m.group(1) if date_m else None),
                "deceased_name": dec_val,
                "doctor_name": "Forensic Medical Examiner",
                "findings": ["Laceration on occipital region"],
                "opinion_text": "Death due to traumatic injuries.",
                "status": "Conducted",
                "is_applicable": True,
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 6. FSL REPORT PARSER
        if '"fslreport"' in prompt_cf or 'examined_items' in prompt_cf:
            rep_m = re.search(r'(?:FSL Report No\.?|Report No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', body_text, re.I)
            date_m = re.search(r'(?:Date Of Report|Date Of Examination|Date Of Receipt|Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)
            lab_m = re.search(r'(?:Laboratory|Lab)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            items_m = re.search(r'(?:Examined Items)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            items = [i.strip() for i in items_m.group(1).split(",")] if items_m else ["Forensic exhibit 1"]

            raw_dict = {
                "report_number": rep_m.group(1).strip() if rep_m else "FSL-01",
                "report_date": _normalize_date_str(date_m.group(1) if date_m else None),
                "laboratory_name": lab_m.group(1).strip() if lab_m else "Forensic Science Laboratory",
                "examined_items": items,
                "findings": ["Authentic evidentiary material without signs of tampering"],
                "opinion_text": "Forensic analysis confirms evidentiary consistency.",
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 7. SEIZURE MEMO PARSER
        if '"seizurememo"' in prompt_cf or 'seized_items' in prompt_cf:
            memo_m = re.search(r'(?:Memo No\.?|Memo Id|Report No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', body_text, re.I) or re.search(r'(?:Memo No\.?|Memo Id|Report No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', ocr_text, re.I)
            loc_m = re.search(r'(?:Location of Seizure|Place|Location)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            by_m = re.search(r'SEIZING OFFICER[\s\S]*?Name:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'(?:Prepared by|Officer)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            by_val = "Investigating Officer"
            if by_m:
                cand = by_m.group(1).strip().strip(",-")
                if cand and cand.rstrip(":").casefold() not in ("none", "nil", "name", "unknown", "n/a"):
                    by_val = cand
            date_m = re.search(r'(?:Date Of Seizure|Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)
            time_m = re.search(r'(?:Time)[:\s\r\n]+(\d{1,2}[:.]\d{2})', body_text, re.I)
            sz_time = "14:00:00"
            if time_m:
                t_parts = time_m.group(1).replace(".", ":").split(":")
                sz_time = f"{int(t_parts[0]):02d}:{int(t_parts[1]):02d}:00"

            vehicles = re.findall(r'\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4})\b', body_text)

            seized = []
            desc_matches = re.findall(r'(?:Description|Item Description)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            id_matches = re.findall(r'(?:Evidence Id|Exhibit Mark|Exhibit)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            if desc_matches:
                for idx, desc in enumerate(desc_matches):
                    d_clean = desc.strip().strip(",-")
                    if d_clean and d_clean.casefold() not in ("none", "nil", "unknown", "n/a"):
                        ex_mark = id_matches[idx].strip() if idx < len(id_matches) else f"Ex-{idx+1}"
                        seized.append({"description": d_clean, "exhibit_mark": ex_mark})
            elif vehicles:
                for idx, v in enumerate(set(vehicles), 1):
                    seized.append({"description": f"Vehicle {v}", "exhibit_mark": f"V{idx}"})

            raw_dict = {
                "memo_number": memo_m.group(1).strip() if memo_m else "SZ-01",
                "seizure_datetime": f"{_normalize_date_str(date_m.group(1) if date_m else None)}T{sz_time}",
                "seizure_location": loc_m.group(1).strip() if loc_m else "Crime Scene",
                "seized_items": seized,
                "prepared_by": by_val,
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 8. VEHICLE INSPECTION PARSER
        if '"vehicleinspection"' in prompt_cf or 'vehicle_registration' in prompt_cf:
            rep_m = re.search(r'(?:Report No\.?|Report Id|Inspection Report No\.?|VIR/)[:\s\r\n]*([A-Z0-9/\-]+)', body_text, re.I)
            date_m = re.search(r'(?:Date Of Inspection|Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)
            vehicles = re.findall(r'\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4})\b', body_text)
            clean_v = [v.replace(' ', '') for v in vehicles]
            v_reg = clean_v[0] if clean_v else None

            by_m = re.search(r'INSPECTING OFFICER[\s\S]*?Name:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'(?:Inspected by|Inspecting Officer)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            by_val = "Transport Authority Inspector"
            if by_m:
                cand = by_m.group(1).strip().strip(",-")
                if cand and cand.rstrip(":").casefold() not in ("none", "nil", "name", "unknown", "n/a"):
                    by_val = cand
            obs_m = re.search(r'(?:Observations|Damage)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            obs_list = [obs_m.group(1).strip()] if obs_m else ["Accident impact damage observed."]

            raw_dict = {
                "report_number": rep_m.group(1).strip() if rep_m else "VIR-01",
                "inspection_date": _normalize_date_str(date_m.group(1) if date_m else None),
                "vehicle_registration": v_reg,
                "inspected_by": by_val,
                "observations": obs_list,
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 9. SITE PLAN PARSER
        if '"siteplan"' in prompt_cf or 'plan_number' in prompt_cf:
            plan_m = re.search(r'(?:Plan No\.?|Plan Id|Report No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', body_text, re.I)
            loc_m = re.search(r'(?:Location)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            by_m = re.search(r'(?:Prepared by|Officer)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            date_m = re.search(r'(?:Date Prepared|Plan Date|Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)

            raw_dict = {
                "plan_number": plan_m.group(1).strip() if plan_m else "SP-01",
                "plan_date": _normalize_date_str(date_m.group(1) if date_m else None),
                "location": loc_m.group(1).strip() if loc_m else "Scene of Incident",
                "prepared_by": by_m.group(1).strip() if by_m else "Investigating Officer",
                "annotations": ["Point A: Primary incident spot", "Point B: Exhibit recovery location"],
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 10. SPOT PANCHNAMA PARSER
        if '"spotpanchnama"' in prompt_cf or 'observations' in prompt_cf and 'witnesses' in prompt_cf:
            memo_m = re.search(r'(?:Panchnama Id|Memo No\.?|Report No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', body_text, re.I)
            loc_m = re.search(r'(?:Place|Location)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            wit_m = re.search(r'(?:Witnesses|Panch Witnesses)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            date_m = re.search(r'(?:Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)
            time_m = re.search(r'(?:Time Started|Time)[:\s\r\n]+(\d{1,2}[:.]\d{2})', body_text, re.I)
            pn_time = "11:00:00"
            if time_m:
                t_parts = time_m.group(1).replace(".", ":").split(":")
                pn_time = f"{int(t_parts[0]):02d}:{int(t_parts[1]):02d}:00"
            witnesses = [w.strip() for w in wit_m.group(1).split(",")] if wit_m else ["Panch Witness 1", "Panch Witness 2"]

            raw_dict = {
                "memo_number": memo_m.group(1).strip() if memo_m else "SP-01",
                "inspection_datetime": f"{_normalize_date_str(date_m.group(1) if date_m else None)}T{pn_time}",
                "location": loc_m.group(1).strip() if loc_m else "Spot of Incident",
                "observations": ["Physical inspection conducted at scene; exhibits photographed."],
                "witnesses": witnesses,
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 11. ARREST MEMO PARSER
        if '"arrestmemo"' in prompt_cf or 'arrested_person_name' in prompt_cf:
            memo_m = re.search(r'(?:Arrest Id|Memo No\.?|Report No\.?)[:\s\r\n]+([A-Z0-9/\-]+)', body_text, re.I)
            arr_m = re.search(r'ARRESTED PERSON[\s\S]*?Name:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'(?:Arrested Person Name|Arrested Person|Accused)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            arr_val = "Accused Person"
            if arr_m:
                val = re.split(r'\s*(?:Alias|Age|Address|\n)', arr_m.group(1))[0].strip().strip(",-")
                if val and len(val) > 1 and val.casefold() not in ("none", "nil", "name:", "unknown", "n/a"):
                    arr_val = val

            loc_m = re.search(r'(?:Place Of Arrest|Location of Arrest|Location|Place)[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            by_m = re.search(r'ARRESTING OFFICER[\s\S]*?Name:[\s\r\n]+([^\r\n]+)', body_text, re.I) or re.search(r'(?:Arresting Officer Name|Arresting Officer|Officer)[:\s\r\n]+([^\r\n,]+)', body_text, re.I)
            date_m = re.search(r'(?:Date Of Arrest|Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)
            time_m = re.search(r'(?:Time Of Arrest|Time)[:\s\r\n]+(\d{1,2}[:.]\d{2})', body_text, re.I)
            arr_time = "19:15:00"
            if time_m:
                t_parts = time_m.group(1).replace(".", ":").split(":")
                arr_time = f"{int(t_parts[0]):02d}:{int(t_parts[1]):02d}:00"

            fn_m = re.search(r'Father(?:\s*Name)?[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            arr_fn = fn_m.group(1).strip() if fn_m else None
            age_m = re.search(r'Age[:\s\r\n]+(\d+)', body_text, re.I)
            arr_age = age_m.group(1).strip() if age_m else None
            addr_m = re.search(r'Address[:\s\r\n]+([^\r\n]+)', body_text, re.I)
            arr_addr = addr_m.group(1).strip() if addr_m else None

            raw_dict = {
                "memo_number": memo_m.group(1).strip() if memo_m else "AR-01",
                "arrest_datetime": f"{_normalize_date_str(date_m.group(1) if date_m else None)}T{arr_time}",
                "arrested_person_name": arr_val,
                "arrest_location": loc_m.group(1).strip() if loc_m else "Police Station",
                "arresting_officer_name": by_m.group(1).strip() if by_m else "Investigating Officer",
                "father_name": arr_fn,
                "age": arr_age,
                "address": arr_addr,
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 12. CASE DIARY PARSER
        if '"casediary"' in prompt_cf or 'diary_number' in prompt_cf:
            cd_m = re.search(r'(?:Diary No\.?|Case Diary No\.?)[:\s]+([A-Z0-9/\-]+)', body_text, re.I)
            by_m = re.search(r'(?:Officer)[:\s]+([^\r\n,]+)', body_text, re.I)
            date_m = re.search(r'(?:Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)
            cd_date = _normalize_date_str(date_m.group(1) if date_m else None) or "2024-10-16"

            raw_dict = {
                "diary_number": cd_m.group(1).strip() if cd_m else "CD-01",
                "officer_name": by_m.group(1).strip() if by_m else "Investigating Officer",
                "entries": [
                    {
                        "entry_number": "1",
                        "entry_datetime": f"{cd_date}T09:00:00",
                        "text": body_text[:200].strip(),
                    }
                ],
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)

        # 13. CCTV METADATA PARSER
        if '"cctvmetadata"' in prompt_cf or 'camera_identifier' in prompt_cf:
            cam_m = re.search(r'(?:Camera ID|Camera Identifier)[:\s]+([A-Z0-9/\-]+)', body_text, re.I)
            loc_m = re.search(r'(?:Location)[:\s]+([^\r\n]+)', body_text, re.I)
            dt_m = re.search(r'(?:Recording Date & Time|Date & Time|Date Of Collection|Date)[:\s\r\n]+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})', body_text, re.I)
            cctv_date = _normalize_date_str(dt_m.group(1) if dt_m else None) or "2024-10-15"

            raw_dict = {
                "camera_identifier": cam_m.group(1).strip() if cam_m else "CAM-01",
                "recording_datetime": f"{cctv_date}T18:20:00",
                "location": loc_m.group(1).strip() if loc_m else "Traffic Junction",
                "duration_seconds": 120.0,
                "metadata_text": body_text[:200].strip(),
                "confidence": 0.95,
            }
            return self._sanitize_entities(raw_dict, ocr_text)
        return {"confidence": 0.90}
