# ai-report-generator/backend/app/core/prompt_builder.py
from typing import Dict, Any

class PromptBuilder:
    """
    Builds structured prompts for the LLM to generate technical report content.
    """
    
    def build_prompt(self, title: str, project_type: str, description: str) -> str:
        """
        Convert user input into a structured technical report instruction.
        
        Args:
            title: Project title
            project_type: Either 'academic' or 'industrial'
            description: Detailed project description
            
        Returns:
            Formatted prompt string for LLM
        """
        prompt = f"""
You are an expert technical report writer. Generate a comprehensive {project_type} report with the following title:

TITLE: {title}
PROJECT TYPE: {project_type}
DESCRIPTION: {description}

Generate a complete technical report with the following sections in JSON format. Each section should be concise and professional:

{{
    "abstract": "Brief summary of the entire project (100-150 words)",
    "introduction": "Background and context (150-200 words)",
    "problem_statement": "Clear problem definition (100-150 words)",
    "objectives": ["Objective 1", "Objective 2", "Objective 3", ...] (3-4 clear objectives)",
    "methodology": "Brief approach description (200-250 words)",
    "tools_technologies": ["Tool/Technology 1", "Tool/Technology 2", ...] (list main tools used)",
    "system_architecture": "High-level design description (150-200 words)",
    "implementation": "Key implementation details (200-250 words)",
    "results_analysis": "Main results and insights (150-200 words)",
    "conclusion": "Summary of findings (100-150 words)",
    "future_scope": "Future directions (100-150 words)",
    "charts_needed": [
        {{"type": "bar", "title": "Performance Metrics", "data": {{"categories": ["Metric1", "Metric2"], "values": [85, 92]}}}},
        {{"type": "line", "title": "Growth Trends", "data": {{"x": [1,2,3,4,5], "y": [10,25,45,70,100]}}}}
    ]
}}

Ensure the total content length corresponds to approximately 8-10 pages when formatted.
Make the content realistic, technical, and professional.
"""
        return prompt.strip()