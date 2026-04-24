# ai-report-generator/backend/app/pdf/pdf_builder.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle
from reportlab.platypus import KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from typing import Dict, Any, List
import logging
from datetime import datetime
from app.pdf.styles import get_styles
from app.pdf.layouts import CoverPage, TableOfContents

logger = logging.getLogger(__name__)

class PDFBuilder:
    """
    Builds professional PDF reports using ReportLab Platypus.
    """
    
    def __init__(self):
        self.styles = get_styles()
        self.page_width, self.page_height = A4
        self.chart_placeholder = "[CHART]"
        
    def create_pdf(self, content: Dict[str, Any], images: List[Dict[str, str]], output_path: str):
        """
        Create a complete PDF report.
        
        Args:
            content: Dictionary containing report content sections
            images: List of dicts with 'path' and 'title' for each image
            output_path: Path where PDF will be saved
        """
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Create the PDF document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=54,  # Slightly smaller margins to allow more content per line
                leftMargin=54,
                topMargin=72,
                bottomMargin=72,
                title=content.get('title', 'Technical Report'),
                author='AI Report Generator'
            )
            
            # Build story elements
            story = self._build_story(content, images)
            # Build PDF
            doc.build(
                story,
                onFirstPage=self._header_footer,
                onLaterPages=self._header_footer
            )
            
            logger.info(f"PDF generated successfully: {output_path}")
            
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise
    def _build_story(self, content: Dict[str, Any], images: List[Dict[str, str]]) -> List:
        """Build the story elements for the PDF."""
        story = []
        
        # Add cover page
        story.extend(CoverPage.create(
            title=content.get('title', 'Technical Report'),
            date=datetime.now().strftime("%B %d, %Y")
        ))
        
        # Add table of contents placeholder
        story.extend(TableOfContents.create())
        story.append(PageBreak())
        
        # Add sections
        sections = [
            ('Abstract', 'abstract'),
            ('Introduction', 'introduction'),
            ('Problem Statement', 'problem_statement'),
            ('Objectives', 'objectives'),
            ('Methodology', 'methodology'),
            ('Tools & Technologies', 'tools_technologies'),
            ('System Architecture', 'system_architecture'),
            ('Implementation', 'implementation'),
            ('Results & Analysis', 'results_analysis'),
            ('Future Scope', 'future_scope'),
            ('Conclusion', 'conclusion')
        ]
        
        for section_title, section_key in sections:
            # Add section heading
            story.append(Paragraph(section_title, self.styles['Heading1']))
            story.append(Spacer(1, 0.2 * inch))
            
            # Add section content
            section_content = content.get(section_key, '')
            
            if isinstance(section_content, list):
                if section_key in ['objectives', 'tools_technologies']:
                    # Handle flat list items (objectives, tools)
                    for item in section_content:
                        bullet_text = f"• {item}"
                        story.append(Paragraph(bullet_text, self.styles['Normal']))
                        story.append(Spacer(1, 0.1 * inch))
                else:
                    # Handle nested subsections
                    for sub in section_content:
                        sub_title = sub.get('sub_title', '') if isinstance(sub, dict) else ''
                        sub_text = sub.get('content', '') if isinstance(sub, dict) else str(sub)
                        
                        # Ensure sub_text is always a string
                        if isinstance(sub_text, list):
                            sub_text = '\n\n'.join(str(item) for item in sub_text)
                        elif not isinstance(sub_text, str):
                            sub_text = str(sub_text)
                        
                        if sub_title:
                            story.append(Paragraph(sub_title, self.styles['Heading2']))
                            story.append(Spacer(1, 0.1 * inch))
                            
                        # Handle paragraph text in subsection
                        paragraphs = sub_text.split('\n\n')
                        for para in paragraphs:
                            if para.strip():
                                story.append(Paragraph(para, self.styles['Normal']))
                                story.append(Spacer(1, 0.1 * inch))
                        story.append(Spacer(1, 0.15 * inch))
            else:
                # Handle plain text paragraph (mostly for abstract)
                paragraphs = str(section_content).split('\n\n')
                for para in paragraphs:
                    if para.strip():
                        story.append(Paragraph(para, self.styles['Normal']))
                        story.append(Spacer(1, 0.1 * inch))
            
            # Add images to Results & Analysis section
            if section_key == 'results_analysis' and images:
                story.append(Spacer(1, 0.3 * inch))
                self._add_images_to_story(story, images)
            
            story.append(Spacer(1, 0.2 * inch))

            # Add images to relevant sections (usually near results)
            if section_key == 'results_analysis' and images:
                story.append(Spacer(1, 0.3 * inch))
                self._add_images_to_story(story, images)
            
            story.append(Spacer(1, 0.2 * inch))
        
        return story
        
        return story
    
    def _add_images_to_story(self, story: List, images: List[Dict[str, str]]):
        """Add AI-generated images to the story with proper formatting."""
        for i, img_data in enumerate(images):
            img_path = img_data.get("path", "")
            img_title = img_data.get("title", f"Figure {i + 1}")
            
            if img_path and os.path.exists(img_path):
                try:
                    # Add figure title
                    story.append(Paragraph(
                        f"Figure {i + 1}: {img_title}",
                        self.styles['FigureTitle']
                    ))
                    story.append(Spacer(1, 0.1 * inch))
                    
                    # Add image
                    img = Image(img_path, width=5.5*inch, height=3.7*inch)
                    story.append(img)
                    story.append(Spacer(1, 0.2 * inch))
                    
                except Exception as e:
                    logger.error(f"Failed to add image {img_path}: {e}")
    
    def _header_footer(self, canvas_obj, doc):
        """Add header and footer to each page."""
        canvas_obj.saveState()
        
        # Add page number
        page_num = canvas_obj.getPageNumber()
        text = f"Page {page_num}"
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.drawRightString(self.page_width - 72, 40, text)
        
        # Add report title in header (except on cover page)
        if page_num > 1:
            canvas_obj.setFont('Helvetica', 8)
            canvas_obj.setFillColor(colors.grey)
            canvas_obj.drawString(72, self.page_height - 40, "Technical Report")
        
        canvas_obj.restoreState()
