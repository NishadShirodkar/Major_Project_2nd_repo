"""Formal ReportLab/Platypus renderer for the evidence-backed charge sheet."""

from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

from ..chargesheet.form_if5_schema import ChargeSheetData, ChargeSheetField, IF5Row


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas recording total pages to draw accurate 'Page X of Y'."""

    _is_final: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        # Top banner line
        self.setStrokeColor(colors.HexColor("#94A3B8"))
        self.setLineWidth(0.45)
        self.line(15 * mm, A4[1] - 13 * mm, A4[0] - 15 * mm, A4[1] - 13 * mm)

        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))

        if self._is_final:
            header_text = "BYOMKESH AI - FORMAL INVESTIGATION CHARGE SHEET (FINALIZED)"
        else:
            header_text = "BYOMKESH AI - CHARGE SHEET (DRAFT - NOT COURT FILED)"
        self.drawString(15 * mm, A4[1] - 10 * mm, header_text)

        # Bottom footer line
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.35)
        self.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)

        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        if self._is_final:
            self.drawString(15 * mm, 8.5 * mm, "CONFIDENTIAL & STATUTORY RECORD - FINAL APPROVED COPY")
        else:
            self.drawString(15 * mm, 8.5 * mm, "INVESTIGATION DRAFT ONLY - SUBJECT TO REVIEW & OFFICIAL APPROVAL")

        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 15 * mm, 8.5 * mm, page_str)
        self.restoreState()


def _make_canvas_class(is_final: bool):
    class ConfiguredCanvas(NumberedCanvas):
        _is_final = is_final
    return ConfiguredCanvas


class IF5Renderer:
    """Render existing ChargeSheetData only; this class never changes its meaning."""

    _MAX_TABLE_ROW_TEXT_LENGTH = 1200

    def render(self, data: ChargeSheetData, output: Path, *, final: bool = False) -> Path:
        if data.disposition == "final_blocked":
            raise ValueError("FINAL_BLOCKED cases cannot render a charge sheet")
        output.parent.mkdir(parents=True, exist_ok=True)
        styles = self._styles()
        story = [Spacer(1, 16 * mm), Paragraph("CHARGE SHEET", styles["DocumentTitle"])]
        status = f"FINALIZED / APPROVED VERSION {data.version}" if final else f"DRAFT / REVIEW COPY - VERSION {data.version}"
        story += [
            Paragraph(status, styles["Status"]),
            Spacer(1, 5 * mm),
            self._case_information(data, styles),
            Spacer(1, 5 * mm),
            HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#64748B")),
            Spacer(1, 4 * mm),
        ]
        self._text_section(story, "Case Summary", data.case_summary, styles)
        self._text_section(story, "Detailed Facts", data.detailed_facts, styles)
        self._text_section(story, "Investigation Conducted", data.investigation_conducted, styles)
        for name, rows in (
            ("Complainant Details", data.complainants),
            ("Victim Details", data.victims),
            ("Accused Details", data.accused),
            ("Witness Details", data.witnesses),
            ("Chronological Timeline", data.timeline),
            ("Documentary Evidence", data.documentary_evidence),
            ("Material Evidence", data.material_evidence),
        ):
            self._table_section(story, name, rows, styles)
        for name, fields in (
            ("Medical Findings", data.medical_findings),
            ("Forensic Findings", data.forensic_findings),
            ("Vehicle Findings", data.vehicle_findings),
        ):
            self._findings_section(story, name, fields, styles)
        self._text_section(story, "Evidence Analysis", data.evidence_analysis, styles)
        self._findings_section(story, "Applicable Sections", data.legal_sections, styles)
        self._legal_findings_section(story, data.legal_findings, styles)
        self._review_items_section(story, "Conflicts Requiring Review", data.conflicts, styles)
        self._review_items_section(story, "Missing Information", data.missing_information, styles)
        story.append(PageBreak())
        self._table_section(story, "Annexure Index", data.annexures, styles)
        story += [
            Spacer(1, 6 * mm),
            HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94A3B8")),
            Spacer(1, 4 * mm),
            Paragraph(self._paragraph_text(f"Final Opinion of Investigating Officer: {data.final_opinion.rendered}"), styles["Body"]),
            Spacer(1, 5 * mm),
            Paragraph(self._paragraph_text(f"Signature: {data.signature.rendered}"), styles["Body"]),
        ]
        if final:
            story += [
                Spacer(1, 6 * mm),
                HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#1E3A5F")),
                Spacer(1, 3 * mm),
                Paragraph("<b>STATUTORY CERTIFICATION & ADMINISTRATIVE ENDORSEMENT</b>", styles["FieldLabel"]),
                Paragraph(
                    f"This document represents the finalized, verified, and officially approved investigation charge sheet (Version {data.version}). "
                    f"All evidence exhibits, witness accounts, and applicable statutory provisions have been reviewed and validated. "
                    f"This record is finalized and protected from further inline modification.",
                    styles["Small"],
                ),
            ]

        document = BaseDocTemplate(
            str(output),
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=22 * mm,
            bottomMargin=17 * mm,
            title="Charge Sheet Final" if final else "Charge Sheet Draft",
        )
        frame = Frame(document.leftMargin, document.bottomMargin, document.width, document.height, id="body")
        document.addPageTemplates(PageTemplate(id="charge-sheet", frames=[frame]))
        document.build(story, canvasmaker=_make_canvas_class(final))
        return output

    @staticmethod
    def _styles():
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="DocumentTitle", parent=styles["Title"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=17, leading=21, spaceAfter=3 * mm, textColor=colors.HexColor("#0F172A")))
        styles.add(ParagraphStyle(name="Status", parent=styles["Normal"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.HexColor("#475569")))
        styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=3 * mm, spaceAfter=2 * mm, textColor=colors.HexColor("#172554")))
        styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=9.3, leading=13, spaceAfter=1.5 * mm))
        styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=7.8, leading=9.6))
        styles.add(ParagraphStyle(name="TableHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.2, leading=10, textColor=colors.white))
        styles.add(ParagraphStyle(name="RecordHeading", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.HexColor("#172554"), spaceBefore=2 * mm, spaceAfter=1 * mm))
        styles.add(ParagraphStyle(name="FieldLabel", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.4, leading=10.5, textColor=colors.HexColor("#334155"), spaceBefore=1 * mm, spaceAfter=0.5 * mm))
        return styles

    def _case_information(self, data: ChargeSheetData, styles):
        cells = (("Case Number", data.case_number), ("Police Station", data.police_station), ("Court", data.court))
        rows = [[Paragraph(self._paragraph_text(name), styles["Small"]), Paragraph(self._render_field_value(field), styles["Body"])] for name, field in cells]
        table = Table(rows, colWidths=[38 * mm, 142 * mm], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return table

    def _heading(self, story: list, heading: str, styles) -> None:
        story.extend([Paragraph(heading, styles["Section"]), HRFlowable(width="100%", thickness=0.35, color=colors.HexColor("#CBD5E1")), Spacer(1, 1.5 * mm)])

    def _text_section(self, story: list, heading: str, field: ChargeSheetField, styles) -> None:
        heading_text = heading
        if getattr(field, "origin", None) == "reviewer_corrected":
            heading_text += " [Reviewer Corrected]"
        self._heading(story, heading_text, styles)
        lines = field.rendered.splitlines()
        if heading == "Investigation Conducted":
            for statement in (line.strip() for line in lines if line.strip()):
                story.append(Paragraph(self._paragraph_text(statement), styles["Body"], bulletText="•"))
            story.append(Spacer(1, 3 * mm))
            return
        for line in lines:
            clean = line.strip()
            if clean.startswith("- "):
                story.append(Paragraph(self._paragraph_text(clean[2:]), styles["Body"], bulletText="•"))
            elif clean.endswith(":"):
                story.append(Paragraph(self._paragraph_text(clean), styles["FieldLabel"]))
            elif clean:
                story.append(Paragraph(self._paragraph_text(clean), styles["Body"]))
        story.append(Spacer(1, 3 * mm))

    def _findings_section(self, story: list, heading: str, fields: tuple[ChargeSheetField, ...], styles) -> None:
        self._heading(story, heading, styles)
        values = fields or (ChargeSheetField(status="unavailable", review_required=True),)
        for field in values:
            story.append(Paragraph(self._render_field_value(field), styles["Body"], bulletText="•"))
        story.append(Spacer(1, 3 * mm))

    def _table_section(self, story: list, heading: str, rows: tuple[IF5Row, ...], styles) -> None:
        self._heading(story, heading, styles)
        rendered_rows = rows or (IF5Row(serial=1, description=ChargeSheetField(status="unavailable", review_required=True), exhibit=ChargeSheetField(status="not_applicable", review_required=True)),)
        if any(self._requires_structured_row(row) for row in rendered_rows):
            self._structured_rows(story, rendered_rows, styles)
            return
        headers = {
            "Complainant Details": ("S.No.", "Complainant Particulars", "Role / Record Reference"),
            "Victim Details": ("S.No.", "Victim Particulars & Injuries", "Medical / Hospital Reference"),
            "Accused Details": ("S.No.", "Accused Particulars (Name, Age, Address)", "Arrest & Custody Status"),
            "Witness Details": ("S.No.", "Witness Name & Particulars", "Statement / Examination Ref"),
            "Chronological Timeline": ("S.No.", "Date, Time & Occurrence Details", "Corroborating Evidence"),
            "Documentary Evidence": ("S.No.", "Document Description & Scope", "Exhibit Mark / Ref"),
            "Material Evidence": ("S.No.", "Property Description & Seizure Spot", "Exhibit Mark / Custody"),
            "Annexure Index": ("S.No.", "Document Title & Scope", "Annexure / Exhibit No."),
        }
        h_sno, h_desc, h_exh = headers.get(heading, ("S.No.", "Description", "Exhibit / Reference"))
        table_data = [[Paragraph(h_sno, styles["TableHeader"]), Paragraph(h_desc, styles["TableHeader"]), Paragraph(h_exh, styles["TableHeader"])]]
        table_data += [[Paragraph(str(row.serial), styles["Small"]), Paragraph(self._render_field_value(row.description), styles["Small"]), Paragraph(self._render_field_value(row.exhibit), styles["Small"])] for row in rendered_rows]
        table = Table(table_data, colWidths=[15 * mm, 120 * mm, 45 * mm], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94A3B8")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        story.extend([table, Spacer(1, 3 * mm)])

    def _requires_structured_row(self, row: IF5Row) -> bool:
        """Avoid ReportLab table rows that cannot split when one cell is very long."""
        return max(len(row.description.rendered), len(row.exhibit.rendered)) > self._MAX_TABLE_ROW_TEXT_LENGTH

    def _structured_rows(self, story: list, rows: tuple[IF5Row, ...], styles) -> None:
        """Render unbounded row content as independently splittable flowables."""
        for row in rows:
            story.append(HRFlowable(width="100%", thickness=0.35, color=colors.HexColor("#94A3B8"), spaceBefore=1 * mm, spaceAfter=1 * mm))
            story.append(Paragraph(f"S.No. {row.serial}", styles["RecordHeading"]))
            self._labelled_value(story, "Description", row.description.rendered, styles)
            self._labelled_value(story, "Exhibit", row.exhibit.rendered, styles)
        story.append(Spacer(1, 3 * mm))

    def _labelled_value(self, story: list, label: str, value: str, styles) -> None:
        story.append(Paragraph(label, styles["FieldLabel"]))
        story.append(Paragraph(self._paragraph_text(value), styles["Body"]))

    def _render_field_value(self, field: ChargeSheetField) -> str:
        text = self._paragraph_text(field.rendered)
        if getattr(field, "origin", None) == "reviewer_corrected":
            text += ' <font color="#B45309"><b>[Reviewer Corrected]</b></font>'
        return text

    @staticmethod
    def _paragraph_text(value: str) -> str:
        return escape(value).replace("\n", "<br/>")

    def _legal_findings_section(self, story: list, findings, styles) -> None:
        if not findings:
            return
        self._heading(story, "Legal Findings & Statutory Reasoning", styles)
        for index, finding in enumerate(findings, 1):
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94A3B8"), spaceBefore=1 * mm, spaceAfter=1 * mm))
            story.append(Paragraph(f"Legal Finding {index}", styles["RecordHeading"]))
            self._labelled_value(story, "Offence / Section", f"{finding.offence.rendered}\n{finding.proposed_section.rendered}", styles)
            self._labelled_value(story, "Finding Status", finding.status, styles)
            self._labelled_value(story, "Offence Description", finding.description.rendered, styles)
            self._labelled_value(story, "Evidence Strength", finding.evidence_strength, styles)
            if finding.offence.confidence is not None:
                self._labelled_value(story, "Confidence", f"{finding.offence.confidence:.2f}", styles)
            self._labelled_value(story, "Review Required", "Yes" if finding.review_required else "No", styles)

            if getattr(finding, "reasoning_summary", None):
                self._labelled_value(story, "Statutory Analysis & Reasoning", finding.reasoning_summary, styles)

            assessments = getattr(finding, "ingredient_assessments", ())
            if assessments:
                story.append(Paragraph("Statutory Ingredients Assessment", styles["FieldLabel"]))
                for item in assessments:
                    name = item.get("ingredient_name") or item.get("name", "Ingredient")
                    st = item.get("status", "REQUIRES_REVIEW")
                    desc = item.get("description", "")
                    color_tag = "#16A34A" if st == "SUPPORTED" else ("#DC2626" if st == "NOT_ESTABLISHED" else "#D97706")
                    ing_line = f"• <b>{escape(name)}</b> [<font color='{color_tag}'><b>{escape(st)}</b></font>]: {escape(desc)}"
                    story.append(Paragraph(ing_line, styles["Body"]))
                    for sf in item.get("supporting_facts", ()):
                        story.append(Paragraph(f"<i>Supporting:</i> {escape(sf)}", styles["Small"], bulletText="-"))
                    for mf in item.get("missing_facts", ()):
                        story.append(Paragraph(f"<i>Missing:</i> {escape(mf)}", styles["Small"], bulletText="?"))
                    for rp in item.get("retrieved_passages", ())[:2]:
                        p_text = rp.get("text", "")[:110]
                        p_doc = rp.get("document_name", "Document")
                        p_page = rp.get("page_number", 1)
                        p_cat = rp.get("relevance_category", "supporting")
                        cat_color = "#16A34A" if p_cat == "supporting" else "#DC2626"
                        story.append(Paragraph(f"<i>Retrieved [{escape(p_doc)} p.{p_page} - <font color='{cat_color}'>{p_cat}</font>]:</i> {escape(p_text)}...", styles["Small"], bulletText="→"))

            self._evidence_items(story, "Supporting Evidence", finding.supporting_evidence, styles)
            if finding.contradicting_evidence:
                self._evidence_items(story, "Contradicting / Exculpatory Evidence", finding.contradicting_evidence, styles)

            missing_ev = getattr(finding, "missing_evidence", ())
            if missing_ev:
                story.append(Paragraph("Missing Statutory Evidence", styles["FieldLabel"]))
                for item in missing_ev:
                    story.append(Paragraph(self._paragraph_text(str(item)), styles["Body"], bulletText="!"))

            warnings = getattr(finding, "review_warnings", ())
            if warnings:
                story.append(Paragraph("Reviewer Warnings & Procedural Alerts", styles["FieldLabel"]))
                for warn in warnings:
                    story.append(Paragraph(self._paragraph_text(str(warn)), styles["Body"], bulletText="▲"))

        story.append(Spacer(1, 3 * mm))

    def _evidence_items(self, story: list, heading: str, fields: tuple[ChargeSheetField, ...], styles) -> None:
        story.append(Paragraph(heading, styles["FieldLabel"]))
        if not fields:
            story.append(Paragraph("Not Available in Investigation Records", styles["Body"]))
            return
        for field in fields:
            story.append(Paragraph(self._paragraph_text(field.rendered), styles["Body"], bulletText="•"))

    def _review_items_section(self, story: list, heading: str, items, styles) -> None:
        if not items:
            return
        self._heading(story, heading, styles)
        for item in items:
            story.append(Paragraph(self._paragraph_text(item.description), styles["Body"], bulletText="•"))
        story.append(Spacer(1, 3 * mm))
