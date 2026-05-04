import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.pdf.layouts import CoverPage, TableOfContents
from app.pdf.styles import get_styles

logger = logging.getLogger(__name__)


class PDFBuilder:
    """
    Renders the canonical 11-chapter report into a polished PDF.

    Expected `content` shape (matches `ReportContent`):
        {
            "title": str,
            "project_type": str,
            "abstract": str,
            "chapters": [
                {
                    "number": int,
                    "key": str,
                    "title": str,
                    "subsections": [{"number": str, "title": str, "content": str}, ...]
                },
                ...
            ]
        }
    """

    RESULTS_CHAPTER_KEY = "results_discussion"

    def __init__(self):
        self.styles = get_styles()
        self.page_width, self.page_height = A4

    def create_pdf(
        self,
        content: Dict[str, Any],
        images: List[Dict[str, str]],
        output_path: str,
    ) -> None:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=54,
                leftMargin=54,
                topMargin=72,
                bottomMargin=72,
                title=content.get("title", "Technical Report"),
                author="AI Report Generator",
            )
            story = self._build_story(content, images)
            doc.build(
                story,
                onFirstPage=self._header_footer,
                onLaterPages=self._header_footer,
            )
            logger.info("PDF generated successfully: %s", output_path)
        except Exception as e:
            logger.error("PDF generation failed: %s", e)
            raise

    def _build_story(
        self, content: Dict[str, Any], images: List[Dict[str, str]]
    ) -> List:
        story: List[Any] = []

        # Cover page
        story.extend(
            CoverPage.create(
                title=content.get("title", "Technical Report"),
                date=datetime.now().strftime("%B %d, %Y"),
            )
        )

        chapters = content.get("chapters", [])

        # Table of contents derived from canonical structure
        toc_entries = [("Abstract", None)]
        toc_entries.extend(
            (f"{ch['number']}. {ch['title']}", None) for ch in chapters
        )
        story.extend(TableOfContents.create(toc_entries))

        # Abstract
        story.append(Paragraph("Abstract", self.styles["Heading1"]))
        story.append(Spacer(1, 0.2 * inch))
        for paragraph in str(content.get("abstract", "")).split("\n\n"):
            text = paragraph.strip()
            if text:
                story.append(Paragraph(text, self.styles["Normal"]))
                story.append(Spacer(1, 0.1 * inch))
        story.append(PageBreak())

        # Chapters
        for chapter in chapters:
            self._render_chapter(story, chapter)
            if chapter.get("key") == self.RESULTS_CHAPTER_KEY and images:
                story.append(Spacer(1, 0.3 * inch))
                self._add_images_to_story(story, images)
            story.append(PageBreak())

        return story

    def _render_chapter(self, story: List, chapter: Dict[str, Any]) -> None:
        heading = f"{chapter.get('number', '')}. {chapter.get('title', '')}".strip(". ")
        story.append(Paragraph(heading, self.styles["Heading1"]))
        story.append(Spacer(1, 0.2 * inch))

        for sub in chapter.get("subsections", []):
            sub_heading = f"{sub.get('number', '')} {sub.get('title', '')}".strip()
            story.append(Paragraph(sub_heading, self.styles["Heading2"]))
            story.append(Spacer(1, 0.1 * inch))

            for block in sub.get("blocks", []) or []:
                self._render_block(story, block)
            story.append(Spacer(1, 0.15 * inch))

    def _render_block(self, story: List, block: Dict[str, Any]) -> None:
        if not isinstance(block, dict):
            return
        btype = block.get("type")

        if btype == "paragraph":
            text = str(block.get("text") or "").strip()
            if not text:
                return
            for paragraph in text.split("\n\n"):
                p = paragraph.strip()
                if not p:
                    continue
                story.append(Paragraph(p, self.styles["Normal"]))
                story.append(Spacer(1, 0.08 * inch))
            return

        if btype in {"ordered_list", "unordered_list"}:
            items = [
                str(item).strip()
                for item in (block.get("items") or [])
                if str(item).strip()
            ]
            if not items:
                return
            list_items = [
                ListItem(
                    Paragraph(item, self.styles["Normal"]),
                    leftIndent=18,
                    spaceBefore=2,
                    spaceAfter=2,
                )
                for item in items
            ]
            if btype == "ordered_list":
                flowable = ListFlowable(
                    list_items,
                    bulletType="1",
                    leftIndent=24,
                    bulletFontName="Helvetica-Bold",
                    bulletFontSize=11,
                )
            else:
                flowable = ListFlowable(
                    list_items,
                    bulletType="bullet",
                    start="•",
                    leftIndent=24,
                    bulletFontName="Helvetica-Bold",
                    bulletFontSize=11,
                )
            story.append(flowable)
            story.append(Spacer(1, 0.1 * inch))

    def _add_images_to_story(
        self, story: List, images: List[Dict[str, str]]
    ) -> None:
        for i, img_data in enumerate(images):
            img_path = img_data.get("path", "")
            img_title = img_data.get("title", f"Figure {i + 1}")
            if not img_path or not os.path.exists(img_path):
                continue
            try:
                story.append(
                    Paragraph(
                        f"Figure {i + 1}: {img_title}",
                        self.styles["FigureTitle"],
                    )
                )
                story.append(Spacer(1, 0.1 * inch))
                story.append(Image(img_path, width=5.5 * inch, height=3.7 * inch))
                story.append(Spacer(1, 0.2 * inch))
            except Exception as e:
                logger.error("Failed to add image %s: %s", img_path, e)

    def _header_footer(self, canvas_obj, doc) -> None:
        canvas_obj.saveState()

        page_num = canvas_obj.getPageNumber()
        canvas_obj.setFont("Helvetica", 9)
        canvas_obj.drawRightString(self.page_width - 72, 40, f"Page {page_num}")

        if page_num > 1:
            canvas_obj.setFont("Helvetica", 8)
            canvas_obj.setFillColor(colors.grey)
            canvas_obj.drawString(72, self.page_height - 40, "Technical Report")

        canvas_obj.restoreState()
