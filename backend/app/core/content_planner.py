# ai-report-generator/backend/app/core/content_planner.py
from typing import Dict, Any, List
import math

class ContentPlanner:
    """
    Plans and distributes content to ensure appropriate report length.
    """
    
    def __init__(self, target_pages: int = 15):
        self.target_pages = target_pages
        self.words_per_page = 400  # Average words per page with formatting
        
    def plan_content(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Distribute content across sections to achieve target page count.
        
        Args:
            llm_response: Raw LLM response with content sections
            
        Returns:
            Processed content with balanced section lengths
        """
        # Ensure all required sections exist
        content = self._ensure_sections(llm_response)
        
        # Calculate word counts for visibility
        total_words = self._count_total_words(content)
        estimated_pages = round(total_words / self.words_per_page, 2)
        print(f"\n[DENSITY CHECK] Total Words: {total_words} | Estimated Pages: {estimated_pages}")
        
        # Condense only if extremely long
        target_words = self.target_pages * self.words_per_page
        if total_words > target_words * 1.5:  # Be more lenient with length
            print(f"[CLEANUP] Condensing content as it exceeds {target_words} targets...")
            content = self._condense_content(content, total_words - target_words)
        
        # Add placeholder markers for charts
        content = self._add_chart_placeholders(content)
        
        return content
    
    def _ensure_sections(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure critical sections exist, and allow all other AI content."""
        # Baseline check
        if "abstract" not in content or not content["abstract"]:
            content["abstract"] = "Technical analysis summary pending."
            
        # We no longer inject placeholders. This keeps the report clean if a section is skipped.
        return content
    
    def _count_total_words(self, content: Dict[str, Any]) -> int:
        """Count total words in all sections and nested subsections."""
        total = 0
        
        for key, value in content.items():
            if key in ["image_prompts", "title", "project_type", "charts_needed"]:
                continue
                
            if isinstance(value, str):
                total += len(value.split())
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        total += len(item.split())
                    elif isinstance(item, dict) and "content" in item:
                        # Handle nested subsection content
                        total += len(str(item["content"]).split())
                        
        return total
    
    def _condense_content(self, content: Dict[str, Any], excess_words: int) -> Dict[str, Any]:
        """Condense content by removing redundant information if exceeding target."""
        # For nested structure, we condense the largest subsections
        for key, value in content.items():
            if isinstance(value, list) and key not in ["image_prompts", "objectives", "tools_technologies"]:
                for sub in value:
                    if isinstance(sub, dict) and "content" in sub:
                        words = str(sub["content"]).split()
                        if len(words) > 800:  # Only condense if a single sub-section is massive
                            sub["content"] = " ".join(words[:750]) + "... [condensed]"
            elif isinstance(value, str) and key == "abstract":
                words = value.split()
                if len(words) > 400:
                    content[key] = " ".join(words[:350]) + "..."
        
        return content
    
    def _add_chart_placeholders(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Add image placeholder markers in relevant sections."""
        if "image_prompts" in content and content["image_prompts"]:
            # Add image references in results_analysis section
            if "results_analysis" in content:
                image_refs = ""
                for i, img in enumerate(content["image_prompts"]):
                    title = img.get("title", f"Figure {i+1}") if isinstance(img, dict) else f"Figure {i+1}"
                    image_refs += f"\n[IMAGE: {title}]"
                
                # Handle hierarchical list vs flat string
                if isinstance(content["results_analysis"], list):
                    if content["results_analysis"]:
                        # Append to the last subsection
                        last_sub = content["results_analysis"][-1]
                        if isinstance(last_sub, dict) and "content" in last_sub:
                            last_sub["content"] += "\n\n" + image_refs.strip()
                        else:
                            content["results_analysis"].append({"sub_title": "Visual Analysis", "content": image_refs.strip()})
                    else:
                        content["results_analysis"].append({"sub_title": "Visual Analysis", "content": image_refs.strip()})
                else:
                    # Fallback for flat string
                    content["results_analysis"] += "\n\n" + image_refs.strip()
        
        return content
