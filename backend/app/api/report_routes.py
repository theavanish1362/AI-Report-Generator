# ai-report-generator/backend/app/api/report_routes.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from app.models.report_schema import ReportRequest, ReportResponse
from app.core.content_planner import ContentPlanner
from app.core.llm_client import LLMClient
from app.core.prompt_builder import PromptBuilder
from app.generators.image_generator import ImageGenerator
from app.pdf.pdf_builder import PDFBuilder
from app.utils.file_utils import FileUtils
import logging
import uuid
import os
import json
import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate-report", response_model=ReportResponse)
async def generate_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate a professional PDF report based on project description.
    """
    try:
        # Validate input
        if not request.description or len(request.description.strip()) == 0:
            raise HTTPException(status_code=400, detail="Description cannot be empty")
        
        if len(request.description) > 5000:
            raise HTTPException(status_code=400, detail="Description too long (max 5000 characters)")
        
        # Add logging for monitoring
        logger.info(f"[API] Received request: Title='{request.title}', Pages={request.pages}")
        
        # Initialize components
        llm_client = LLMClient()
        prompt_builder = PromptBuilder()
        content_planner = ContentPlanner(target_pages=request.pages)
        # Generate unique IDs for files early for use in generators
        report_id = str(uuid.uuid4())
        pdf_filename = f"report_{report_id}.pdf"
        pdf_path = os.path.join("generated_reports", pdf_filename)
        pdf_builder = PDFBuilder()
        
        # Determine generation strategy
        if request.pages > 8: # Lowered threshold for better quality
            print(f"\n[STRATEGY] Multi-Stage Iterative Generation (Target: {request.pages} pages)")
            from app.core.section_generator import SectionGenerator
            section_gen = SectionGenerator()
            llm_response = await section_gen.generate_full_report(request)
        else:
            print(f"\n[STRATEGY] Single-Shot Generation (Target: {request.pages} pages)")
            prompt = prompt_builder.build_prompt(
                title=request.title,
                project_type=request.project_type,
                description=request.description,
                pages=request.pages
            )
            # Inject required fields before validation to prevent Pydantic errors
            llm_response = await llm_client.generate_content(prompt, validate_schema=False)
            llm_response['title'] = request.title
            llm_response['project_type'] = request.project_type
            
            # Now validate once we've injected the missing pieces
            from app.models.report_schema import ReportContent
            try:
                ReportContent.model_validate(llm_response)
                logger.info("JSON Structure validated successfully after injection.")
            except Exception as ve:
                logger.warning(f"JSON Structure still imperfect but proceeding: {ve}")
        
        # Final safety check for title
        if 'title' not in llm_response:
            llm_response['title'] = request.title
        
        # Plan content structure
        content = content_planner.plan_content(llm_response)
        
        # Skip image generation per user request
        images = []
        
        # Build PDF
        pdf_builder.create_pdf(
            content=content,
            images=images,
            output_path=pdf_path
        )
        
        # Save metadata
        metadata = {
            "id": report_id,
            "title": request.title,
            "date": datetime.datetime.now().isoformat(),
            "type": request.project_type,
            "pages": request.pages
        }
        metadata_path = os.path.join("generated_reports", f"report_{report_id}.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
        
        return ReportResponse(
            success=True,
            message="Report generated successfully",
            pdf_path=pdf_path,
            report_id=report_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.get("/download/{report_id}")
async def download_report(report_id: str):
    """Download a generated report by ID."""
    pdf_path = os.path.join("generated_reports", f"report_{report_id}.pdf")
    
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Report not found")
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"report_{report_id}.pdf"
    )

@router.get("/history")
async def get_history():
    """Get all generated reports history."""
    reports = []
    reports_dir = "generated_reports"
    if not os.path.exists(reports_dir):
        return reports
        
    for filename in os.listdir(reports_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(reports_dir, filename)
            try:
                with open(file_path, "r") as f:
                    reports.append(json.load(f))
            except Exception as e:
                logger.error(f"Failed to read metadata {file_path}: {e}")
                
    # Sort by date descending
    reports.sort(key=lambda x: x.get("date", ""), reverse=True)
    return reports

@router.delete("/report/{report_id}")
async def delete_report(report_id: str):
    """Delete a report by ID."""
    pdf_path = os.path.join("generated_reports", f"report_{report_id}.pdf")
    json_path = os.path.join("generated_reports", f"report_{report_id}.json")
    
    deleted = False
    
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        deleted = True
        
    if os.path.exists(json_path):
        os.remove(json_path)
        deleted = True
        
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
        
    return {"success": True, "message": "Report deleted successfully"}
