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
        
        # Calculate current total words
        total_words = self._count_total_words(content)
        target_words = self.target_pages * self.words_per_page
        
        # Adjust content if needed
        if total_words < target_words:
            content = self._expand_content(content, target_words - total_words)
        elif total_words > target_words * 1.2:  # Allow 20% overflow
            content = self._condense_content(content, total_words - target_words)
        
        # Add placeholder markers for charts
        content = self._add_chart_placeholders(content)
        
        return content
    
    def _ensure_sections(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all required sections are present."""
        required_sections = [
            "abstract", "introduction", "problem_statement", "objectives",
            "methodology", "tools_technologies", "system_architecture",
            "implementation", "results_analysis", "conclusion", "future_scope",
            "charts_needed"
        ]
        
        for section in required_sections:
            if section not in content:
                if section == "objectives":
                    content[section] = ["Objective 1", "Objective 2", "Objective 3"]
                elif section == "tools_technologies":
                    content[section] = ["Python", "FastAPI", "OpenAI"]
                elif section == "charts_needed":
                    content[section] = []
                else:
                    content[section] = f"Content for {section} will be developed here."
        
        return content
    
    def _count_total_words(self, content: Dict[str, Any]) -> int:
        """Count total words in all sections."""
        total = 0
        
        for key, value in content.items():
            if key == "charts_needed":
                continue
                
            if isinstance(value, str):
                total += len(value.split())
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        total += len(item.split())
                        
        return total
    
    def _expand_content(self, content: Dict[str, Any], additional_words: int) -> Dict[str, Any]:
        """Expand content by adding more details to each section."""
        # Distribute additional words proportionally
        sections = [s for s in content.keys() if s != "charts_needed" and isinstance(content[s], str)]
        
        if not sections:
            return content
            
        words_per_section = additional_words // len(sections)
        
        for section in sections:
            if isinstance(content[section], str):
                # Add more detailed content
                expansion = f"\n\nFurther analysis reveals that {section} demonstrates significant importance in the overall project context. Additional considerations include scalability, performance optimization, and integration with existing systems. The implementation approach ensures robust handling of edge cases while maintaining high performance standards."
                content[section] += expansion
        
        return content
    
    def _condense_content(self, content: Dict[str, Any], excess_words: int) -> Dict[str, Any]:
        """Condense content by removing redundant information."""
        # Simple implementation - in production, use more sophisticated summarization
        for key in content.keys():
            if key != "charts_needed" and isinstance(content[key], str):
                words = content[key].split()
                if len(words) > 300:  # Condense long sections
                    content[key] = " ".join(words[:250]) + "... [content condensed for brevity]"
        
        return content
    
    def _add_chart_placeholders(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Add chart placeholder markers in relevant sections."""
        if "charts_needed" in content and content["charts_needed"]:
            # Add chart references in results_analysis section
            if "results_analysis" in content:
                chart_refs = "\n\n[CHART: Performance Metrics - Bar Chart]\n"
                chart_refs += "[CHART: Growth Trends - Line Chart]\n"
                content["results_analysis"] += chart_refs
        
        return content