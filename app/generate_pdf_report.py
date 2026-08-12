# ==============================================================================
# Script Name: dspace_pdf_generator.py
# Version:     1.1.0
# Date:        2026-07-23
# Author:      Oleh Riabtsev / AI Assistant
# Description: PDF Meldebogen / Stammblatt Generator conforming strictly to
#              University of Vechta Corporate Design Manual (v2023) and d.3 DMS rules.
# ==============================================================================

import html
import logging
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# === ОФІЦІЙНА ПАЛІТРА UNIVERITÄT VECHTA (HAUSFARBEN) ===
COLOR_UNI_RED = colors.HexColor("#C10B25")         # CMYK 0/100/80/20 - Основний червоний акцент
COLOR_UNI_BLACK = colors.HexColor("#000000")       # CMYK 0/0/0/100 - Основний текст
COLOR_UNI_GRAY = colors.HexColor("#888888")        # CMYK 0/0/0/60 - Допоміжний сірий
COLOR_UNI_LIGHT_GRAY = colors.HexColor("#EDEDED")  # CMYK 0/0/0/10 - Фон плашок і таблиць


class NumberedCanvas(canvas.Canvas):
    """
    Кастомний Canvas для двопрохідної нумерації сторінок ('Seite X von Y')
    та оформлення верхніх/нижніх колонтитулів за гайдлайнами Uni Vechta.
    """

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

    def draw_page_decorations(self, page_count):
        self.saveState()

        page_width, page_height = A4
        margin = 1.5 * cm

        # --- ВЕРХНІЙ КОЛОНТИТУЛ (HEADER) ---
        self.setFont("Helvetica-Bold", 10)
        self.setFillColor(COLOR_UNI_RED)
        self.drawString(margin, page_height - 1.2 * cm, "Universität Vechta")

        self.setFont("Helvetica-Oblique", 8)
        self.setFillColor(COLOR_UNI_GRAY)
        self.drawString(margin + 3.3 * cm, page_height - 1.2 * cm, "University of Vechta")

        # --- НИЖНІЙ КОЛОНТИТУЛ (FOOTER) ---
        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_UNI_GRAY)

        # Червона акцентна лінія над футером
        self.setStrokeColor(COLOR_UNI_RED)
        self.setLineWidth(1.0)
        self.line(margin, 1.3 * cm, page_width - margin, 1.3 * cm)

        footer_left = "VeRO — Drittmittelverwaltung / Projektanzeige (Meldebogen)"
        footer_right = f"Seite {self._pageNumber} von {page_count}"

        self.drawString(margin, 0.8 * cm, footer_left)
        self.drawRightString(page_width - margin, 0.8 * cm, footer_right)

        self.restoreState()


class VeROPDFGenerator:
    """Модуль генерації PDF-документів (Meldebogen) за стандартом Uni Vechta."""

    @staticmethod
    def _format_cell_text(text: str) -> str:
        """Екранування спецсимволів та форматування переносів рядків."""
        if not text:
            return "-"
        escaped = html.escape(str(text))
        return escaped.replace("\n", "<br/>")

    @classmethod
    def generate_pdf(cls, pdf_groups_data: list, output_filepath: str, vero_id: str = "UNBEKANNT", title: str = "") -> bool:
        """
        Генерує офіційний PDF-файл Meldebogen за структурою 6 груп з DSpaceToD3Mapper.
        """
        try:
            doc = SimpleDocTemplate(
                output_filepath,
                pagesize=A4,
                leftMargin=1.5 * cm,
                rightMargin=1.5 * cm,
                topMargin=1.8 * cm,
                bottomMargin=1.8 * cm
            )

            styles = getSampleStyleSheet()

            # --- СТИЛІ СТИЛІЗАЦІЇ UNI VECHTA ---
            doc_title_style = ParagraphStyle(
                'DocTitle',
                parent=styles['Heading1'],
                fontName='Helvetica-Bold',
                fontSize=15,
                leading=18,
                textColor=COLOR_UNI_RED,
                spaceAfter=2
            )

            betreff_style = ParagraphStyle(
                'DocBetreff',
                parent=styles['Normal'],
                fontName='Helvetica-Bold',
                fontSize=10,
                leading=13,
                textColor=COLOR_UNI_BLACK,
                spaceAfter=4
            )

            meta_style = ParagraphStyle(
                'DocMeta',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=8.5,
                leading=11,
                textColor=COLOR_UNI_GRAY,
                spaceAfter=8
            )

            group_header_style = ParagraphStyle(
                'GroupHeader',
                parent=styles['Heading2'],
                fontName='Helvetica-Bold',
                fontSize=10.5,
                leading=13,
                textColor=COLOR_UNI_RED,
                spaceBefore=8,
                spaceAfter=4
            )

            cell_label_style = ParagraphStyle(
                'CellLabel',
                parent=styles['Normal'],
                fontName='Helvetica-Bold',
                fontSize=8.0,
                leading=10.5,
                textColor=COLOR_UNI_BLACK
            )

            cell_val_style = ParagraphStyle(
                'CellValue',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=8.0,
                leading=10.5,
                textColor=COLOR_UNI_BLACK
            )

            story = []

            # --- 1. ШАПКА ДОКУМЕНТА ---
            story.append(Paragraph("Projektanzeige / Meldebogen", doc_title_style))

            # Формуємо Betreff за рекомендацією Андреаса: "[Projektbezeichnung]/Meldebogen"
            betreff_text = f"Betreff: {title}/Meldebogen" if title else f"Betreff: Meldebogen ({vero_id})"
            story.append(Paragraph(html.escape(betreff_text), betreff_style))

            creation_date = datetime.now().strftime("%d.%m.%Y %H:%M")
            meta_text = f"<b>Vero_ID:</b> {vero_id} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Dokumenttyp:</b> Meldebogen &nbsp;&nbsp;|&nbsp;&nbsp; <b>Datum:</b> {creation_date}"
            story.append(Paragraph(meta_text, meta_style))

            # Червоний розділювач
            story.append(HRFlowable(
                width="100%",
                thickness=1.2,
                color=COLOR_UNI_RED,
                spaceBefore=0,
                spaceAfter=6
            ))

            # --- 2. РЕНДЕРИНГ 6 ГРУП ТАБЛИЦІ ---
            col_widths = [6.2 * cm, 11.8 * cm]  # Разом 18.0 см (Ширина A4 мінус відступи)

            for group in pdf_groups_data:
                group_name = group.get("group_name", "")
                fields = group.get("fields", [])

                if not fields:
                    continue

                story.append(Paragraph(group_name, group_header_style))

                table_data = []
                for field in fields:
                    lbl = field.get("label", "")
                    val = cls._format_cell_text(field.get("value", ""))

                    p_lbl = Paragraph(lbl, cell_label_style)
                    p_val = Paragraph(val, cell_val_style)

                    table_data.append([p_lbl, p_val])

                # Базовий стиль таблиці за гайдлайнами Corporate Design
                t_style = TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('BACKGROUND', (0, 0), (0, -1), COLOR_UNI_LIGHT_GRAY),  # Світло-сіра плашка для назв полів
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                    ('TOPPADDING', (0, 0), (-1, -1), 3.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ])

                # Чергування фону правій колонці для зручності читання
                for row_idx in range(len(table_data)):
                    if row_idx % 2 == 1:
                        t_style.add('BACKGROUND', (1, row_idx), (1, row_idx), colors.HexColor("#FAFAFA"))

                table = Table(table_data, colWidths=col_widths, style=t_style)
                story.append(table)
                story.append(Spacer(1, 4))

            # Побудова PDF з двопрохідним кастомним канвасом
            doc.build(story, canvasmaker=NumberedCanvas)
            logging.info(f" PDF Meldebogen успішно згенеровано: {output_filepath}")
            return True

        except Exception as e:
            logging.error(f"Помилка під час генерації PDF: {str(e)}", exc_info=True)
            return False


# === ТЕСТОВИЙ ЗАПУСК ===
if __name__ == "__main__":
    from dspace_to_d3_mapper import DSpaceToD3Mapper

    sample_dspace_data = {
        "workflow_item_id": 53,
        "item_info": {
            "uuid": "a9044950-83aa-46ce-88ad-da8468e83d5e"
        },
        "metadata": {
            "dc.title": ["D3 Programe Integration"],
            "veroAP.acronym": ["D3PI"],
            "veroAP.fundingAmount": ["100000 €"],
            "veroAP.funding.funderlist": ["Bundesministerium der Finanzen (BMF)"],
            "veroAP.email.contact": ["oleh.riabtsev@uni-vechta.de"],
            "dc.description.provenance": [
                "Submitted by Oleh Riabtsev on 2026-07-22T10:18:52Z",
                "Approved customReviewStep on 2026-07-22T10:20:17Z",
                "Approved customEditStep on 2026-07-22T10:22:28Z",
                "Approved customFinalEditStep on 2026-07-22T10:23:23Z"
            ]
        }
    }

    # Складання структури та генерація файлу
    pdf_data = DSpaceToD3Mapper.get_pdf_report_data(sample_dspace_data)
    v_id = sample_dspace_data["item_info"]["uuid"]
    proj_title = sample_dspace_data["metadata"]["dc.title"][0]

    filename = f"Meldebogen_{v_id[:8]}.pdf"
    VeROPDFGenerator.generate_pdf(
        pdf_groups_data=pdf_data,
        output_filepath=filename,
        vero_id=v_id,
        title=proj_title
    )