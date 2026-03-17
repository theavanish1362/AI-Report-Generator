# ai-report-generator/backend/README.md
# AI Report Generator - Backend

## Overview
FastAPI-based backend service that generates professional PDF reports using OpenAI and ReportLab.

## Features
- Generate 10-20 page technical reports from project descriptions
- Structured sections with proper formatting
- Automatic chart generation (bar and line charts)
- Professional PDF output with cover page, TOC, and page numbers
- Support for academic and industrial project types

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt

2. Configure environment variables

3. Run the server: python run.py

4. API Endpoints : 
POST /api/generate-report
Request Body:
    {
    "title": "Project Title",
    "project_type": "academic",
    "description": "Detailed project description..."
    }

Response:
{
    "success": true,
    "message": "Report generated successfully",
    "pdf_path": "generated_reports/report_123.pdf",
    "report_id": "123"
}

GET /api/download/{report_id}


Directory Structure
app/ - Main application code

generated_reports/ - Output PDF files

generated_charts/ - Temporary chart images