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
from app.core.repository_analyzer import RepositoryAnalyzer, RepositoryAnalysisResult
from app.models.report_schema import ReportRequest, ReportResponse
from app.pdf.pdf_builder import PDFBuilder

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory job tracker. State lives only for the lifetime of the process —
# good enough for a single-instance dev server. The persisted record of a
# finished report is the JSON sidecar in `generated_reports/`.
report_jobs: Dict[str, Dict[str, Any]] = {}
report_jobs_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _count_pdf_pages(pdf_path: str) -> Optional[int]:
    try:
        with open(pdf_path, "rb") as f:
            data = f.read()
        return (
            data.count(b"/Type /Page\n")
            + data.count(b"/Type /Page ")
            + data.count(b"/Type/Page")
        ) or None
    except Exception:
        return None


def _build_pdf_to_target_pages(
    pdf_builder: "PDFBuilder",
    content: Dict[str, Any],
    images: list,
    output_path: str,
    target_pages: int,
    max_iterations: int = 3,
    tolerance: int = 2,
    min_words_per_subsection: int = 25,
) -> Optional[int]:
    """
    Build the PDF and, if the rendered page count exceeds the target by more
    than `tolerance` pages, proportionally trim every subsection's blocks and
    rebuild. Bottoms out at `min_words_per_subsection`.
    """
    pdf_builder.create_pdf(content=content, images=images, output_path=output_path)
    actual = _count_pdf_pages(output_path)

    iteration = 0
    while (
        actual is not None
        and actual > target_pages + tolerance
        and iteration < max_iterations
    ):
        iteration += 1
        ratio = max(0.55, target_pages / actual)
        trimmed = ContentPlanner.trim_subsections_by_ratio(
            content,
            ratio=ratio,
            min_words_per_subsection=min_words_per_subsection,
        )
        if not trimmed:
            break
        logger.info(
            "[PAGINATION] iteration=%s ratio=%.3f rebuilding (was %s pages, target %s)",
            iteration,
            ratio,
            actual,
            target_pages,
        )
        pdf_builder.create_pdf(content=content, images=images, output_path=output_path)
        actual = _count_pdf_pages(output_path)

    return actual


# ---------------------------------------------------------------------------
# Job state
# ---------------------------------------------------------------------------
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
        "estimated_seconds": request.pages * 5,
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
            new_progress = max(0, min(int(updates["progress"]), 100))
            current_progress = int(job.get("progress", 0))
            updates["progress"] = max(current_progress, new_progress)

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


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------
def _merge_description_with_repo_context(
    description: str, repo_summary: str, max_chars: int = 5000
) -> str:
    context_prefix = "\n\nRepository evidence extracted from uploaded ZIP:\n"
    available = max_chars - len(description) - len(context_prefix)
    if available <= 0:
        return description
    return f"{description}{context_prefix}{repo_summary[:available]}"


async def _parse_report_request(
    raw_request: Request,
) -> Tuple[ReportRequest, Optional[UploadFile]]:
    content_type = raw_request.headers.get("content-type", "").lower()

    if "multipart/form-data" in content_type:
        form = await raw_request.form()
        pages_raw = form.get("pages", 20)
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


# ---------------------------------------------------------------------------
# Generation pipeline
# ---------------------------------------------------------------------------
async def _generate_report_internal(
    request: ReportRequest,
    repo_analysis: Optional[RepositoryAnalysisResult] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> ReportResponse:
    """Generate a PDF for the given request and write the JSON metadata sidecar."""
    if not request.description or len(request.description.strip()) == 0:
        raise HTTPException(status_code=400, detail="Description cannot be empty")
    if len(request.description) > 5000:
        raise HTTPException(
            status_code=400, detail="Description too long (max 5000 characters)"
        )

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

    logger.info(
        "[API] title='%s' pages=%s",
        report_request.title,
        report_request.pages,
    )

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

    from app.core.section_generator import SectionGenerator
    from app.models.report_schema import ReportContent

    section_gen = SectionGenerator(progress_callback=progress_callback)
    llm_response = await section_gen.generate_full_report(report_request)

    llm_response.setdefault("title", report_request.title)
    llm_response.setdefault("project_type", report_request.project_type)

    try:
        ReportContent.model_validate(llm_response)
        logger.info("Canonical report structure validated.")
    except Exception as ve:
        logger.warning("Report structure validation failed: %s", ve)

    content = content_planner.plan_content(llm_response)
    images: list = []

    await _emit_progress(
        progress_callback,
        {
            "phase": "bundling_pdf",
            "message": "Bundling report into PDF",
            "progress": 90,
        },
    )

    actual_pages = _build_pdf_to_target_pages(
        pdf_builder=pdf_builder,
        content=content,
        images=images,
        output_path=pdf_path,
        target_pages=report_request.pages,
    )
    logger.info(
        "[PAGINATION] requested=%s actual=%s delta=%s",
        report_request.pages,
        actual_pages,
        (actual_pages - report_request.pages) if actual_pages else "n/a",
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
        "actual_pages": actual_pages,
        "code_context_used": bool(repo_analysis),
        "code_context_stats": repo_analysis.stats if repo_analysis else None,
    }
    metadata_path = os.path.join("generated_reports", f"report_{report_id}.json")
    os.makedirs("generated_reports", exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
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
            await asyncio.sleep(0.5)

            await _update_job(
                job_id,
                phase="parsing_zip",
                message="Parsing ZIP library...",
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
                sub_steps=[
                    "Analyzing components...",
                    "Detecting tech stack...",
                    "Mapping project structure...",
                ],
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
            sub_steps=[],
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


# ---------------------------------------------------------------------------
# Routes (open — no auth)
# ---------------------------------------------------------------------------
@router.post("/generate-report", response_model=ReportResponse)
async def generate_report(request: Request):
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
        logger.error("Report generation failed: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Report generation failed: {e}"
        )


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
    pdf_path = os.path.join("generated_reports", f"report_{report_id}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"report_{report_id}.pdf",
    )


@router.get("/history")
async def get_history():
    """List all reports recorded as JSON sidecars in `generated_reports/`."""
    reports: list = []
    reports_dir = "generated_reports"
    if not os.path.exists(reports_dir):
        return reports

    for filename in os.listdir(reports_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(reports_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    reports.append(json.load(f))
            except Exception as e:
                logger.error("Failed to read metadata %s: %s", file_path, e)

    reports.sort(key=lambda x: x.get("date", ""), reverse=True)
    return reports


@router.delete("/report/{report_id}")
async def delete_report(report_id: str):
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
