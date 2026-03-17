# ai-report-generator/backend/app/pdf/styles.py
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

def get_styles():
    """
    Define and return all paragraph styles for the report.
    """
    # Get base styles
    styles = getSampleStyleSheet()
    
    # Modify existing styles instead of trying to recreate them
    styles['Heading1'].fontSize = 18
    styles['Heading1'].leading = 22
    styles['Heading1'].textColor = colors.HexColor('#2E86AB')
    styles['Heading1'].spaceAfter = 12
    styles['Heading1'].spaceBefore = 20
    
    styles['Heading2'].fontSize = 16
    styles['Heading2'].leading = 20
    styles['Heading2'].textColor = colors.HexColor('#A23B72')
    styles['Heading2'].spaceAfter = 10
    styles['Heading2'].spaceBefore = 15
    
    styles['Normal'].fontSize = 11
    styles['Normal'].leading = 16
    styles['Normal'].alignment = TA_JUSTIFY
    styles['Normal'].spaceAfter = 8
    
    # Add only custom styles that don't already exist
    # Check if style exists before adding
    if 'CoverTitle' not in styles:
        styles.add(ParagraphStyle(
            name='CoverTitle',
            parent=styles['Title'],
            fontSize=28,
            leading=34,
            textColor=colors.HexColor('#2E86AB'),
            alignment=TA_CENTER,
            spaceAfter=30,
            fontName='Helvetica-Bold'
        ))
    
    if 'CoverSubtitle' not in styles:
        styles.add(ParagraphStyle(
            name='CoverSubtitle',
            parent=styles['Normal'],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            spaceAfter=20,
            fontName='Helvetica'
        ))
    
    if 'CoverInfo' not in styles:
        styles.add(ParagraphStyle(
            name='CoverInfo',
            parent=styles['Normal'],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#333333'),
            alignment=TA_CENTER,
            spaceAfter=10,
            fontName='Helvetica'
        ))
    
    if 'Bullet' not in styles:
        styles.add(ParagraphStyle(
            name='Bullet',
            parent=styles['Normal'],
            fontSize=11,
            leading=16,
            leftIndent=20,
            firstLineIndent=0,
            alignment=TA_LEFT,
            spaceAfter=4,
            fontName='Helvetica'
        ))
    
    if 'FigureTitle' not in styles:
        styles.add(ParagraphStyle(
            name='FigureTitle',
            parent=styles['Normal'],
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#666666'),
            spaceAfter=5,
            fontName='Helvetica-Oblique'
        ))
    
    if 'TableOfContents' not in styles:
        styles.add(ParagraphStyle(
            name='TableOfContents',
            parent=styles['Normal'],
            fontSize=11,
            leading=16,
            leftIndent=0,
            alignment=TA_LEFT,
            spaceAfter=4,
            fontName='Helvetica'
        ))
    
    if 'TOCHeading' not in styles:
        styles.add(ParagraphStyle(
            name='TOCHeading',
            parent=styles['Heading2'],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#2E86AB'),
            spaceAfter=12,
            spaceBefore=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
    
    return styles