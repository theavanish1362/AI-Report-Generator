import asyncio
import copy
import datetime
import json
import logging
import os
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.core.content_planner import ContentPlanner
from app.core.llm_client import LLMClient
from app.core.prompt_builder import PromptBuilder
from app.core.repository_analyzer import RepositoryAnalyzer, RepositoryAnalysisResult
from app.models.report_schema import ReportRequest, ReportResponse
from app.pdf.pdf_builder import PDFBuilder

router = APIRouter()
logger = logging.getLogger(__name__)

report_jobs: Dict[str, Dict[str, Any]] = {}
report_jobs_lock = asyncio.Lock()


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


async def _create_job(job_id: str, request: ReportRequest, has_zip: bool) -> None:
    now = _utc_now_iso()
    job = {
        "job_id": job_id,
        "status": "queued",
        "phase": "queued",
        "message": "Job queued",
        "progress": 0,
        "title": request.title,
        "project_type": request.project_type,
        "pages": request.pages,
        "has_zip": has_zip,
        "report_id": None,
        "pdf_path": None,
        "error": None,
        "chapter_list": [],
        "chapter_details": [],
        "sub_steps": [],
        "current_chapter": None,
        "completed_chapters": 0,
        "total_chapters": 0,
        "start_time": now,
        "estimated_seconds": request.pages * 5,  # Simple estimation: 5s per page
        "events": [
            {
                "phase": "queued",
                "message": "Job queued",
                "progress": 0,
                "timestamp": now,
            }
        ],
        "created_at": now,
        "updated_at": now,
    }
    async with report_jobs_lock:
        report_jobs[job_id] = job


async def _update_job(job_id: str, **updates: Any) -> None:
    async with report_jobs_lock:
        job = report_jobs.get(job_id)
        if not job:
            return

        if "progress" in updates:
            progress = int(updates["progress"])
            updates["progress"] = max(0, min(progress, 100))

        previous_phase = job.get("phase")
        previous_message = job.get("message")
        previous_progress = job.get("progress")

        job.update(updates)
        job["updated_at"] = _utc_now_iso()

        if (
            "phase" in updates
            or "message" in updates
            or "progress" in updates
            or "sub_steps" in updates
        ):
            event = {
                "phase": job.get("phase"),
                "message": job.get("message"),
                "progress": job.get("progress"),
                "sub_steps": job.get("sub_steps", []),
                "timestamp": job["updated_at"],
            }
            if (
                event["phase"] != previous_phase
                or event["message"] != previous_message
                or event["progress"] != previous_progress
            ):
                job["events"].append(event)
                job["events"] = job["events"][-60:]


async def _get_job(job_id: str) -> Optional[Dict[str, Any]]:
    async with report_jobs_lock:
        job = report_jobs.get(job_id)
        if not job:
            return None
        return copy.deepcopy(job)


async def _emit_progress(
    callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]],
    payload: Dict[str, Any],
) -> None:
    if callback is None:
        return
    await callback(payload)


def _merge_description_with_repo_context(description: str, repo_summary: str, max_chars: int = 5000) -> str:
    """
    Append repository context while preserving request limits.
    """
    context_prefix = "\n\nRepository evidence extracted from uploaded ZIP:\n"
    available = max_chars - len(description) - len(context_prefix)
    if available <= 0:
        return description
    return f"{description}{context_prefix}{repo_summary[:available]}"


async def _parse_report_request(raw_request: Request) -> Tuple[ReportRequest, Optional[UploadFile]]:
    """
    Accept both JSON and multipart form-data inputs.
    """
    content_type = raw_request.headers.get("content-type", "").lower()

    if "multipart/form-data" in content_type:
        form = await raw_request.form()
        pages_raw = form.get("pages", 15)
        try:
            pages = int(pages_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="pages must be an integer")

        payload = {
            "title": str(form.get("title", "")),
            "project_type": str(form.get("project_type", "")),
            "description": str(form.get("description", "")),
            "pages": pages,
        }

        try:
            parsed = ReportRequest.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc

        upload_candidate = form.get("project_zip")
        has_upload = bool(upload_candidate and getattr(upload_candidate, "filename", ""))
        return parsed, upload_candidate if has_upload else None

    try:
        payload = await raw_request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid request payload") from exc

    try:
        parsed = ReportRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    return parsed, None


async def _generate_report_internal(
    request: ReportRequest,
    repo_analysis: Optional[RepositoryAnalysisResult] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> ReportResponse:
    """
    Generate a professional PDF report based on project description.
    """
    if not request.description or len(request.description.strip()) == 0:
        raise HTTPException(status_code=400, detail="Description cannot be empty")

    if len(request.description) > 5000:
        raise HTTPException(status_code=400, detail="Description too long (max 5000 characters)")

    report_request = request
    if repo_analysis:
        enriched_description = _merge_description_with_repo_context(
            description=request.description,
            repo_summary=repo_analysis.summary_text,
        )
        report_request = request.model_copy(update={"description": enriched_description})
        logger.info(
            "[CODEBASE] Included analyzed ZIP context: files=%s stack=%s",
            repo_analysis.stats.get("scanned_files"),
            ", ".join(repo_analysis.stats.get("detected_stack", [])) or "unknown",
        )

    logger.info("[API] Received request: Title='%s', Pages=%s", report_request.title, report_request.pages)

    llm_client = LLMClient()
    prompt_builder = PromptBuilder()
    content_planner = ContentPlanner(target_pages=report_request.pages)
    report_id = str(uuid.uuid4())
    pdf_filename = f"report_{report_id}.pdf"
    pdf_path = os.path.join("generated_reports", pdf_filename)
    pdf_builder = PDFBuilder()

    await _emit_progress(
        progress_callback,
        {
            "phase": "planning_report",
            "message": "Preparing report generation plan",
            "progress": 25,
        },
    )

    if report_request.pages > 8:
        print(f"\n[STRATEGY] Multi-Stage Iterative Generation (Target: {report_request.pages} pages)")
        from app.core.section_generator import SectionGenerator

        section_gen = SectionGenerator(progress_callback=progress_callback)
        llm_response = await section_gen.generate_full_report(report_request)
    else:
        print(f"\n[STRATEGY] Single-Shot Generation (Target: {report_request.pages} pages)")
        await _emit_progress(
            progress_callback,
            {
                "phase": "generating_content",
                "message": "Generating report content",
                "progress": 55,
            },
        )
        prompt = prompt_builder.build_prompt(
            title=report_request.title,
            project_type=report_request.project_type,
            description=report_request.description,
            pages=report_request.pages,
        )
        llm_response = await llm_client.generate_content(prompt, validate_schema=False)
        llm_response["title"] = report_request.title
        llm_response["project_type"] = report_request.project_type

        from app.models.report_schema import ReportContent

        try:
            ReportContent.model_validate(llm_response)
            logger.info("JSON Structure validated successfully after injection.")
        except Exception as ve:
            logger.warning("JSON Structure still imperfect but proceeding: %s", ve)

        await _emit_progress(
            progress_callback,
            {
                "phase": "content_generated",
                "message": "Content generated. Building PDF",
                "progress": 85,
            },
        )

    if "title" not in llm_response:
        llm_response["title"] = report_request.title

    content = content_planner.plan_content(llm_response)
    images = []

    await _emit_progress(
        progress_callback,
        {
            "phase": "bundling_pdf",
            "message": "Bundling report into PDF",
            "progress": 90,
        },
    )
    pdf_builder.create_pdf(
        content=content,
        images=images,
        output_path=pdf_path,
    )

    await _emit_progress(
        progress_callback,
        {
            "phase": "completing",
            "message": "Finalizing report artifacts",
            "progress": 96,
        },
    )

    metadata = {
        "id": report_id,
        "title": report_request.title,
        "date": datetime.datetime.now().isoformat(),
        "type": report_request.project_type,
        "pages": report_request.pages,
        "code_context_used": bool(repo_analysis),
        "code_context_stats": repo_analysis.stats if repo_analysis else None,
    }
    metadata_path = os.path.join("generated_reports", f"report_{report_id}.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f)

    return ReportResponse(
        success=True,
        message="Report generated successfully",
        pdf_path=pdf_path,
        report_id=report_id,
    )


async def _run_report_job(
    job_id: str,
    request: ReportRequest,
    zip_payload: Optional[Tuple[str, bytes]],
) -> None:
    try:
        await _update_job(
            job_id,
            status="processing",
            phase="preparing",
            message="Preparing report request",
            progress=5,
        )

        repo_analysis = None
        if zip_payload:
            filename, payload = zip_payload
            await _update_job(
                job_id,
                phase="zip_uploaded",
                message=f"ZIP Uploaded: {filename}",
                progress=5,
            )
            await asyncio.sleep(0.5) # For UI visibility
            
            await _update_job(
                job_id,
                phase="parsing_zip",
                message=f"Parsing ZIP library...",
                progress=10,
            )
            analyzer = RepositoryAnalyzer()
            repo_analysis = analyzer.analyze_archive_bytes(filename, payload)
            
            await _update_job(
                job_id,
                phase="scanning_code",
                message="Scanning code for context...",
                progress=20,
                code_context_stats=repo_analysis.stats,
                sub_steps=["Analyzing components...", "Detecting tech stack...", "Mapping project structure..."]
            )
            await asyncio.sleep(0.5)
        else:
            await _update_job(
                job_id,
                phase="zip_skipped",
                message="No ZIP uploaded.",
                progress=15,
            )

        async def progress_proxy(payload: Dict[str, Any]) -> None:
            await _update_job(job_id, **payload)

        result = await _generate_report_internal(
            request=request,
            repo_analysis=repo_analysis,
            progress_callback=progress_proxy,
        )

        await _update_job(
            job_id,
            status="completed",
            phase="ready_to_download",
            message="Report generation completed",
            progress=100,
            report_id=result.report_id,
            pdf_path=result.pdf_path,
            sub_steps=[]
        )
    except HTTPException as http_error:
        await _update_job(
            job_id,
            status="failed",
            phase="failed",
            message=str(http_error.detail),
            error=str(http_error.detail),
            progress=100,
        )
    except Exception as error:
        logger.exception("Background report generation failed for job %s", job_id)
        await _update_job(
            job_id,
            status="failed",
            phase="failed",
            message="Report generation failed",
            error=str(error),
            progress=100,
        )


@router.post("/generate-report", response_model=ReportResponse)
async def generate_report(
    request: Request,
):
    try:
        parsed_request, project_zip = await _parse_report_request(request)
        repo_analysis = None
        if project_zip:
            analyzer = RepositoryAnalyzer()
            repo_analysis = await analyzer.analyze_upload(project_zip)

        return await _generate_report_internal(parsed_request, repo_analysis)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.post("/generate-report-job")
async def generate_report_job(request: Request):
    parsed_request, project_zip = await _parse_report_request(request)
    zip_payload: Optional[Tuple[str, bytes]] = None

    if project_zip:
        payload = await project_zip.read()
        filename = project_zip.filename or "project.zip"
        await project_zip.close()
        zip_payload = (filename, payload)

    job_id = str(uuid.uuid4())
    await _create_job(job_id, parsed_request, bool(zip_payload))
    asyncio.create_task(_run_report_job(job_id, parsed_request, zip_payload))

    return {
        "success": True,
        "message": "Report generation started",
        "job_id": job_id,
    }


@router.get("/report-status/{job_id}")
async def get_report_status(job_id: str):
    job = await _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


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
