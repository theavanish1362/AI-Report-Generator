# ai-report-generator/backend/app/core/prompt_builder.py
from typing import Dict, Any

class PromptBuilder:
    """
    Builds structured prompts for the LLM to generate technical report content.
    """
    
    def build_outline_prompt(self, title: str, project_type: str, description: str, pages: int) -> str:
        """Phase 1: Generate a comprehensive table of contents with STRICT KEYS."""
        return f"""
Act as a Technical Architect. Create an 8-chapter outline for a {pages}-page report on '{title}'.
PROJECT: {project_type} | DESCRIPTION: {description}

TASK: Return a JSON object with these EXACT keys for your sections:
[introduction, problem_statement, methodology, system_architecture, implementation, results_analysis, future_scope, conclusion]

OUTPUT FORMAT (JSON ONLY):
{{
    "abstract_plan": "Specific strategy for the abstract...",
    "sections": [
        {{ "title": "1. [Specific Title]", "key": "introduction", "subsections": ["Sub A", "Sub B"] }},
        {{ "title": "2. [Specific Title]", "key": "problem_statement", "subsections": ["Sub A", "Sub B"] }},
        ...
    ]
}}
""".strip()

    def build_section_prompt(self, title: str, section_title: str, subsections: list, target_words: int) -> str:
        """Phase 2: Generate deep content for a specific chapter."""
        subs_str = ", ".join(subsections)
        return f"""
Write the '{section_title}' chapter for a technical report titled '{title}'.
SUB-CHAPTERS TO COVER: {subs_str}
TARGET LENGTH: {target_words} words. (MASSIVE, EXHAUSTIVE TECHNICAL DETAIL REQUIRED).

QUALITY RULES:
1. Provide deep technical insights and data-driven explanations.
2. Every sub-chapter MUST have at least 8-10 expansive paragraphs.
3. Your goal is 1500+ words. If you are brief, you have FAILED.
4. Each chapter must focus on unique technical aspects to avoid duplicate headings.

OUTPUT JSON FORMAT:
[
    {{ "sub_title": "Subsection Title", "content": "1500+ words of granular technical analysis..." }},
    ...
]
""".strip()

    def build_prompt(self, title: str, project_type: str, description: str, pages: int) -> str:
        """
        Convert user input into a structured technical report instruction.
        """
        # Calculate target word density
        total_target_words = pages * 400
        words_per_section_avg = total_target_words // 9
        
        prompt = f"""
You are an expert technical report writer. Generate a comprehensive {project_type} report.

TITLE: {title}
PROJECT TYPE: {project_type}
DESCRIPTION: {description}
TARGET LENGTH: {pages} pages (Must reach approx. {total_target_words} words total)

### REQUIRED NESTED STRUCTURE EXAMPLE (STRICT JSON ONLY):
For every major section, use this list-of-objects structure:
"introduction": [
    {{"sub_title": "1.1 Project Overview", "content": "3-4 detailed paragraphs discussing X, Y, and Z..."}},
    {{"sub_title": "1.2 Necessity and Motivation", "content": "3-4 detailed paragraphs discussing A, B, and C..."}}
]

### JSON SCHEMA TO FOLLOW:
{{
    "abstract": "Minimum 250 words summary",
    "introduction": [..nested subsections..],
    "problem_statement": [..nested subsections..],
    "objectives": ["Primary...", "Secondary...", "Technical..."],
    "methodology": [..nested subsections..],
    "tools_technologies": ["Tool A", "Tool B", "Env C"],
    "system_architecture": [..nested subsections..],
    "implementation": [..nested subsections..],
    "results_analysis": [..nested subsections..],
    "conclusion": [..nested subsections..],
    "future_scope": [..nested subsections..]
}}

### CRITICAL RULES:
1. Every section (except Abstract, Objectives, Tools) MUST be a list of objects with "sub_title" and "content".
2. Strings are FORBIDDEN for major section values. 
3. Each subsection content must be expansive and technically deep.
4. Target a total of {total_target_words} words. 
5. Return ONLY valid JSON. Keep the response long.
"""
        return prompt.strip()
