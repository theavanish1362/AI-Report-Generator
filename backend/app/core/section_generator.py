import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.core.llm_client import LLMClient
from app.core.prompt_builder import PromptBuilder
from app.models.report_schema import (
    CANONICAL_OUTLINE,
    Chapter,
    OrderedListBlock,
    ParagraphBlock,
    ReportRequest,
    Subsection,
    UnorderedListBlock,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pagination calibration
# ---------------------------------------------------------------------------
# Anchor points measured against the real ReportLab layout (A4, 11pt body,
# 16pt leading, H1 chapters, H2 subsections, forced PageBreak per chapter).
# Each tuple is (rendered_pages, words_per_subsection_required). The mapping
# is non-linear because chapters absorb extra words until they spill onto a
# new page, so we interpolate between anchors instead of using a constant
# words-per-page. See _calibrate_pages.py for the measurement script.
# ---------------------------------------------------------------------------

STRUCTURAL_MIN_PAGES = 18  # Floor of the canonical 11-chapter layout.

# Lookup of (achievable_pages, words_per_subsection) measured empirically.
# Pages come in discrete steps because each chapter only spills to a new page
# above a certain word threshold; values between steps aren't reachable in
# one shot, so the generator deliberately over-shoots and then iterative
# truncation in the API trims down to the requested count.
PAGE_TO_WPS_LOOKUP = [
    (18, 50),
    (22, 100),
    (26, 125),
    (28, 175),
    (35, 250),
    (37, 325),
    (41, 350),
    (45, 400),
]


def words_per_subsection_for_target(target_pages: int) -> int:
    """
    Pick the smallest per-subsection word target whose rendered page count
    is at least `target_pages`. Caller is expected to iteratively trim if
    the resulting PDF over-shoots the request.
    """
    for pages, wps in PAGE_TO_WPS_LOOKUP:
        if target_pages <= pages:
            return wps
    return PAGE_TO_WPS_LOOKUP[-1][1]


class SectionGenerator:
    """
    Drives generation of every report from the canonical 11-chapter outline.

    The outline is fixed in code; the LLM only produces body text per
    subsection. We assemble Chapter / Subsection objects ourselves so the
    final document is guaranteed to match `ReportContent`'s strict schema.
    """

    def __init__(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ):
        self.llm_client = LLMClient()
        self.prompt_builder = PromptBuilder()
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.progress_lock: Optional[asyncio.Lock] = None
        self.progress_callback = progress_callback
        self.chapter_states: Dict[int, Dict[str, Any]] = {}
        self.completed_sections = 0

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _emit_progress(self, payload: Dict[str, Any]) -> None:
        if not self.progress_callback:
            return
        try:
            await self.progress_callback(payload)
        except Exception as e:
            logger.warning("Progress callback failed: %s", e)

    def _chapter_snapshot_locked(self) -> List[Dict[str, Any]]:
        return [dict(self.chapter_states[idx]) for idx in sorted(self.chapter_states.keys())]

    async def _initialize_chapter_states(self, chapter_titles: List[str]) -> List[Dict[str, Any]]:
        if self.progress_lock is None:
            self.progress_lock = asyncio.Lock()
        async with self.progress_lock:
            self.chapter_states = {
                idx + 1: {
                    "chapter_number": idx + 1,
                    "title": title,
                    "status": "pending",
                    "attempt": 0,
                    "detail": "Waiting in queue",
                    "updated_at": self._now_iso(),
                }
                for idx, title in enumerate(chapter_titles)
            }
            return self._chapter_snapshot_locked()

    async def _update_chapter_state(
        self,
        chapter_number: int,
        title: str,
        status: str,
        detail: str,
        attempt: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if self.progress_lock is None:
            self.progress_lock = asyncio.Lock()
        async with self.progress_lock:
            entry = self.chapter_states.get(
                chapter_number,
                {
                    "chapter_number": chapter_number,
                    "title": title,
                    "status": "pending",
                    "attempt": 0,
                    "detail": "",
                    "updated_at": self._now_iso(),
                },
            )
            entry.update(
                {
                    "title": title,
                    "status": status,
                    "detail": detail,
                    "updated_at": self._now_iso(),
                }
            )
            if attempt is not None:
                entry["attempt"] = attempt
            self.chapter_states[chapter_number] = entry
            return self._chapter_snapshot_locked()

    async def _mark_chapter_completed(
        self, chapter_number: int, total: int, snapshot: List[Dict[str, Any]]
    ) -> None:
        if self.progress_lock is None:
            self.progress_lock = asyncio.Lock()
        async with self.progress_lock:
            self.completed_sections += 1
            completed = self.completed_sections
        progress = min(40 + int((completed / max(total, 1)) * 45), 85)
        await self._emit_progress(
            {
                "phase": "chapter_generation",
                "message": f"Completed chapter {chapter_number}/{total}",
                "progress": progress,
                "current_chapter": chapter_number,
                "completed_chapters": completed,
                "total_chapters": total,
                "chapter_details": snapshot,
            }
        )

    # ------------------------------------------------------------------
    # Coercion: turn whatever the LLM returned into per-subsection blocks
    # ------------------------------------------------------------------
    def _coerce_blocks(self, raw: Any) -> List[Any]:
        """
        Normalise a single subsection's value into a list of ContentBlock
        objects (ParagraphBlock / OrderedListBlock / UnorderedListBlock).
        """
        if raw is None:
            return []

        # Single string -> one paragraph
        if isinstance(raw, str):
            text = raw.strip()
            return [ParagraphBlock(text=text)] if text else []

        # Single dict that is itself a block
        if isinstance(raw, dict):
            block = self._dict_to_block(raw)
            if block is not None:
                return [block]
            # Otherwise: maybe a wrapper like {"blocks": [...]} or {"content": [...]}
            for wrapper in ("blocks", "content", "items"):
                inner = raw.get(wrapper)
                if isinstance(inner, list):
                    return self._coerce_blocks(inner)
            # Fallback: stringify values into a single paragraph
            joined = "\n\n".join(
                str(v).strip() for v in raw.values() if isinstance(v, (str, int, float))
            ).strip()
            return [ParagraphBlock(text=joined)] if joined else []

        if isinstance(raw, list):
            blocks: List[Any] = []
            string_buffer: List[str] = []

            def flush_strings() -> None:
                if string_buffer:
                    text = "\n\n".join(s.strip() for s in string_buffer if s.strip())
                    if text:
                        blocks.append(ParagraphBlock(text=text))
                    string_buffer.clear()

            for item in raw:
                if isinstance(item, str):
                    string_buffer.append(item)
                    continue
                if isinstance(item, dict):
                    flush_strings()
                    block = self._dict_to_block(item)
                    if block is not None:
                        blocks.append(block)
                    else:
                        # Recurse into nested wrappers
                        nested = self._coerce_blocks(item)
                        blocks.extend(nested)
            flush_strings()
            return blocks

        # Anything else: stringify
        text = str(raw).strip()
        return [ParagraphBlock(text=text)] if text else []

    def _dict_to_block(self, item: Dict[str, Any]) -> Optional[Any]:
        """Attempt to interpret a dict as one ContentBlock."""
        block_type = (item.get("type") or "").lower().replace("-", "_")

        if block_type == "paragraph":
            text = item.get("text") or item.get("content") or item.get("body") or ""
            text = str(text).strip()
            return ParagraphBlock(text=text) if text else None

        if block_type in {"ordered_list", "numbered_list", "ordered"}:
            items = self._coerce_items(item.get("items"))
            return OrderedListBlock(items=items) if items else None

        if block_type in {"unordered_list", "bulleted_list", "bullet_list", "list"}:
            items = self._coerce_items(item.get("items"))
            return UnorderedListBlock(items=items) if items else None

        # No explicit type, but looks like a list
        if "items" in item and isinstance(item["items"], list):
            items = self._coerce_items(item["items"])
            return UnorderedListBlock(items=items) if items else None

        # No explicit type, but has prose
        text = item.get("text") or item.get("content") or item.get("body")
        if isinstance(text, str) and text.strip():
            return ParagraphBlock(text=text.strip())

        return None

    @staticmethod
    def _coerce_items(raw: Any) -> List[str]:
        if not isinstance(raw, list):
            return []
        out: List[str] = []
        for it in raw:
            if isinstance(it, str):
                cleaned = it.strip()
            elif isinstance(it, dict):
                cleaned = str(
                    it.get("text") or it.get("content") or it.get("body") or ""
                ).strip()
            else:
                cleaned = str(it).strip()
            if cleaned:
                out.append(cleaned)
        return out

    def _coerce_chapter_data(
        self, raw: Any, chapter_def: Dict[str, Any]
    ) -> Dict[str, List[Any]]:
        # Unwrap common wrappers like {"sections": {...}} or {"report": {...}}
        if isinstance(raw, dict):
            for wrapper in ("subsections", "data", "report", "result", "chapter"):
                inner = raw.get(wrapper)
                if isinstance(inner, (dict, list)):
                    raw = inner
                    break

        result: Dict[str, List[Any]] = {}

        if isinstance(raw, dict):
            for sub in chapter_def["subsections"]:
                num = sub["number"]
                title = sub["title"]
                suffix = num.split(".")[-1]
                candidates = [
                    num,
                    f"{num} {title}",
                    title,
                    title.lower(),
                    suffix,
                ]
                value = None
                for key in candidates:
                    if key in raw:
                        value = raw[key]
                        break
                result[num] = self._coerce_blocks(value)

        elif isinstance(raw, list):
            for sub_def, item in zip(chapter_def["subsections"], raw):
                # Each item might be a dict that already targets a subsection
                if isinstance(item, dict) and "blocks" in item:
                    result[sub_def["number"]] = self._coerce_blocks(item["blocks"])
                else:
                    result[sub_def["number"]] = self._coerce_blocks(item)
            for sub_def in chapter_def["subsections"]:
                result.setdefault(sub_def["number"], [])

        else:
            for sub_def in chapter_def["subsections"]:
                result[sub_def["number"]] = []

        return result

    # ------------------------------------------------------------------
    # Per-chapter generation
    # ------------------------------------------------------------------
    async def _generate_chapter(
        self,
        chapter_def: Dict[str, Any],
        request: ReportRequest,
        target_words: int,
        total: int,
    ) -> Chapter:
        assert self.semaphore is not None
        async with self.semaphore:
            chapter_number = chapter_def["number"]
            chapter_title = chapter_def["title"]

            await self._emit_progress(
                {
                    "phase": f"generating_chapter_{chapter_number}",
                    "message": f"Generating Chapter {chapter_number}: {chapter_title}",
                    "progress": 40 + int(((chapter_number - 1) / max(total, 1)) * 45),
                    "current_chapter": chapter_number,
                    "chapter_title": chapter_title,
                    "total_chapters": total,
                }
            )

            prompt = self.prompt_builder.build_chapter_prompt(
                title=request.title,
                project_type=request.project_type,
                description=request.description,
                chapter=chapter_def,
                target_words=target_words,
            )

            content_map: Dict[str, List[Any]] = {}
            last_error: Optional[Exception] = None
            max_retries = 2

            for attempt in range(max_retries + 1):
                snapshot = await self._update_chapter_state(
                    chapter_number,
                    chapter_title,
                    "running",
                    f"Generating content (attempt {attempt + 1}/{max_retries + 1})",
                    attempt + 1,
                )
                await self._emit_progress(
                    {
                        "phase": f"generating_chapter_{chapter_number}",
                        "message": f"Generating Chapter {chapter_number}: {chapter_title} (attempt {attempt + 1})",
                        "progress": 40 + int(((chapter_number - 1) / max(total, 1)) * 45),
                        "current_chapter": chapter_number,
                        "total_chapters": total,
                        "chapter_details": snapshot,
                    }
                )

                try:
                    raw = await self.llm_client.generate_content(prompt)
                    content_map = self._coerce_chapter_data(raw, chapter_def)
                    if any(content_map.values()):
                        break
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "Chapter %s attempt %s failed: %s", chapter_number, attempt + 1, e
                    )

            subsections = [
                Subsection(
                    number=sub["number"],
                    title=sub["title"],
                    blocks=content_map.get(sub["number"])
                    or [
                        ParagraphBlock(
                            text=f"[Content unavailable for {sub['number']} {sub['title']}]"
                        )
                    ],
                )
                for sub in chapter_def["subsections"]
            ]

            chapter = Chapter(
                number=chapter_number,
                key=chapter_def["key"],
                title=chapter_title,
                subsections=subsections,
            )

            status = "completed" if any(content_map.values()) else "fallback"
            detail = (
                "Chapter generated"
                if status == "completed"
                else f"Used fallback content ({last_error})"
            )
            snapshot = await self._update_chapter_state(
                chapter_number, chapter_title, status, detail
            )
            await self._mark_chapter_completed(chapter_number, total, snapshot)
            return chapter

    # ------------------------------------------------------------------
    # Abstract
    # ------------------------------------------------------------------
    async def _generate_abstract(self, request: ReportRequest) -> str:
        prompt = self.prompt_builder.build_abstract_prompt(
            title=request.title,
            project_type=request.project_type,
            description=request.description,
        )
        try:
            raw = await self.llm_client.generate_content(prompt)
            if isinstance(raw, dict):
                value = raw.get("abstract") or raw.get("content") or ""
                if isinstance(value, list):
                    value = "\n\n".join(str(v) for v in value)
                return str(value).strip()
            return str(raw).strip()
        except Exception as e:
            logger.warning("Abstract generation failed: %s", e)
            return f"This report presents {request.title}. {request.description[:400]}"

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    async def generate_full_report(self, request: ReportRequest) -> Dict[str, Any]:
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(5)
        if self.progress_lock is None:
            self.progress_lock = asyncio.Lock()
        self.completed_sections = 0

        outline = CANONICAL_OUTLINE
        total = len(outline)
        chapter_titles = [f"{c['number']}. {c['title']}" for c in outline]

        snapshot = await self._initialize_chapter_states(chapter_titles)
        await self._emit_progress(
            {
                "phase": "outline_locked",
                "message": "Using canonical 11-chapter outline. Generating chapters",
                "progress": 38,
                "chapter_list": chapter_titles,
                "total_chapters": total,
                "completed_chapters": 0,
                "chapter_details": snapshot,
            }
        )

        # Calibrated per-subsection word target so the rendered PDF lands close
        # to the requested page count.
        words_per_sub = words_per_subsection_for_target(request.pages)
        chapter_targets = [
            words_per_sub * len(c["subsections"]) for c in outline
        ]
        logger.info(
            "[PAGINATION] target_pages=%s words_per_subsection=%s",
            request.pages,
            words_per_sub,
        )

        abstract_task = asyncio.create_task(self._generate_abstract(request))
        chapter_tasks = [
            asyncio.create_task(
                self._generate_chapter(chapter_def, request, target, total)
            )
            for chapter_def, target in zip(outline, chapter_targets)
        ]

        chapters: List[Chapter] = await asyncio.gather(*chapter_tasks)
        abstract = await abstract_task
        chapters.sort(key=lambda c: c.number)

        return {
            "title": request.title,
            "project_type": request.project_type,
            "abstract": abstract,
            "chapters": [c.model_dump() for c in chapters],
        }
