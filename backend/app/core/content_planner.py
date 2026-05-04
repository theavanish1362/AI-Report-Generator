import logging
from typing import Any, Dict, List

from app.core.section_generator import words_per_subsection_for_target

logger = logging.getLogger(__name__)


class ContentPlanner:
    """
    Enforces a per-subsection word budget so the rendered PDF lands close to
    the requested page count, regardless of how verbose the LLM was.

    Subsection content is now a list of typed blocks (paragraph / ordered_list
    / unordered_list). Word counting and truncation work across all blocks.
    """

    OVERRUN_TOLERANCE = 1.15
    ABSTRACT_MAX_WORDS = 320
    MIN_PARAGRAPH_WORDS = 15
    MIN_LIST_ITEM_WORDS = 3

    def __init__(self, target_pages: int = 20):
        self.target_pages = target_pages
        self.budget_per_subsection = words_per_subsection_for_target(target_pages)
        self.hard_cap_per_subsection = int(self.budget_per_subsection * self.OVERRUN_TOLERANCE)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    def plan_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        if not content.get("abstract"):
            content["abstract"] = "Technical analysis summary."

        self._truncate_abstract(content)
        truncated = self._enforce_subsection_budgets(content)

        total_words = self._count_total_words(content)
        logger.info(
            "[PAGINATION] target_pages=%s words_budget_per_sub=%s hard_cap=%s "
            "total_content_words=%s truncated_subsections=%s",
            self.target_pages,
            self.budget_per_subsection,
            self.hard_cap_per_subsection,
            total_words,
            truncated,
        )
        return content

    @staticmethod
    def trim_subsections_by_ratio(
        content: Dict[str, Any],
        ratio: float,
        min_words_per_subsection: int = 25,
    ) -> bool:
        """
        Scale every subsection's total words down by `ratio` (0 < ratio < 1).
        Used by the API's iterative trim-to-target loop. Returns True if any
        subsection was actually trimmed.
        """
        ratio = max(0.0, min(1.0, ratio))
        trimmed = False
        for chapter in content.get("chapters", []):
            for sub in chapter.get("subsections", []):
                blocks = sub.get("blocks") or []
                current = ContentPlanner._words_in_blocks(blocks)
                if current <= 0:
                    continue
                target_words = max(min_words_per_subsection, int(current * ratio))
                if target_words >= current:
                    continue
                sub["blocks"] = ContentPlanner._truncate_blocks(blocks, target_words)
                trimmed = True
        return trimmed

    # ------------------------------------------------------------------
    # Internal: word counting
    # ------------------------------------------------------------------
    def _count_total_words(self, content: Dict[str, Any]) -> int:
        total = 0
        if isinstance(content.get("abstract"), str):
            total += len(content["abstract"].split())
        for chapter in content.get("chapters", []):
            for sub in chapter.get("subsections", []):
                total += self._words_in_blocks(sub.get("blocks", []))
        return total

    @staticmethod
    def _words_in_blocks(blocks: List[Dict[str, Any]]) -> int:
        total = 0
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "paragraph":
                total += len(str(block.get("text", "")).split())
            elif block.get("type") in {"ordered_list", "unordered_list"}:
                for item in block.get("items", []) or []:
                    total += len(str(item).split())
        return total

    # ------------------------------------------------------------------
    # Internal: truncation
    # ------------------------------------------------------------------
    def _truncate_abstract(self, content: Dict[str, Any]) -> None:
        abstract = content.get("abstract")
        if not isinstance(abstract, str):
            return
        words = abstract.split()
        if len(words) > self.ABSTRACT_MAX_WORDS:
            content["abstract"] = " ".join(words[: self.ABSTRACT_MAX_WORDS]) + "..."

    def _enforce_subsection_budgets(self, content: Dict[str, Any]) -> int:
        truncated = 0
        for chapter in content.get("chapters", []):
            for sub in chapter.get("subsections", []):
                blocks = sub.get("blocks") or []
                current_words = self._words_in_blocks(blocks)
                if current_words <= self.hard_cap_per_subsection:
                    continue
                sub["blocks"] = self._truncate_blocks(blocks, self.budget_per_subsection)
                truncated += 1
        return truncated

    @staticmethod
    def _truncate_blocks(
        blocks: List[Dict[str, Any]], budget_words: int
    ) -> List[Dict[str, Any]]:
        """
        Trim a subsection's blocks down to roughly `budget_words` total words.
        Strategy:
          - Walk blocks in order, keeping each whole if it fits, partially
            cropping the block that overflows, dropping any blocks after.
          - For paragraph blocks, crop by word count.
          - For list blocks, drop trailing items first; the last item kept
            may itself be word-cropped if needed.
        """
        if budget_words <= 0:
            return [{"type": "paragraph", "text": "[Content omitted]"}]

        out: List[Dict[str, Any]] = []
        remaining = budget_words

        for block in blocks:
            if not isinstance(block, dict):
                continue
            if remaining <= 0:
                break

            btype = block.get("type")
            if btype == "paragraph":
                text = str(block.get("text", "")).strip()
                if not text:
                    continue
                words = text.split()
                if len(words) <= remaining:
                    out.append({"type": "paragraph", "text": text})
                    remaining -= len(words)
                else:
                    keep = max(ContentPlanner.MIN_PARAGRAPH_WORDS, remaining)
                    cropped = " ".join(words[:keep])
                    if len(words) > keep:
                        cropped += "..."
                    out.append({"type": "paragraph", "text": cropped})
                    remaining = 0

            elif btype in {"ordered_list", "unordered_list"}:
                kept_items: List[str] = []
                for item in block.get("items", []) or []:
                    if remaining <= 0:
                        break
                    item_text = str(item).strip()
                    if not item_text:
                        continue
                    words = item_text.split()
                    if len(words) <= remaining:
                        kept_items.append(item_text)
                        remaining -= len(words)
                    else:
                        keep = max(ContentPlanner.MIN_LIST_ITEM_WORDS, remaining)
                        cropped = " ".join(words[:keep])
                        if len(words) > keep:
                            cropped += "..."
                        kept_items.append(cropped)
                        remaining = 0
                if kept_items:
                    out.append({"type": btype, "items": kept_items})

        if not out:
            out.append({"type": "paragraph", "text": "[Content omitted]"})
        return out
