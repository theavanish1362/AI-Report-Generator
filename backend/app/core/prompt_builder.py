# # ai-report-generator/backend/app/core/prompt_builder.py
# from typing import Dict, Any

# class PromptBuilder:
#     """
#     Builds structured prompts for the LLM to generate technical report content.
#     """
    
#     def build_outline_prompt(self, title: str, project_type: str, description: str, pages: int) -> str:
#         """Phase 1: Generate a comprehensive table of contents with STRICT KEYS."""
#         return f"""
# Act as a Technical Architect. Create an 8-chapter outline for a {pages}-page report on '{title}'.
# PROJECT: {project_type} | DESCRIPTION: {description}

# TASK: Return a JSON object with these EXACT keys for your sections:
# [introduction, problem_statement, methodology, system_architecture, implementation, results_analysis, future_scope, conclusion]

# CRITICAL OUTLINE RULES:
# - You MUST generate exactly 4 to 5 highly detailed 'subsections' for EACH chapter. DO NOT generate just 1 or 2.

# OUTPUT FORMAT (JSON ONLY):
# {{
#     "abstract_plan": "Specific strategy for the abstract...",
#     "sections": [
#         {{ "title": "1. [Specific Title]", "key": "introduction", "subsections": ["Sub-topic A", "Sub-topic B", "Sub-topic C", "Sub-topic D"] }},
#         {{ "title": "2. [Specific Title]", "key": "problem_statement", "subsections": ["Sub-topic A", "Sub-topic B", "Sub-topic C", "Sub-topic D"] }},
#         ...
#     ]
# }}
# """.strip()

#     def build_section_prompt(self, title: str, section_title: str, subsections: list, target_words: int) -> str:
#         """Phase 2: Generate deep content for a specific chapter."""
#         subs_str = ", ".join(subsections)
#         return f"""
# Write the '{section_title}' chapter for a technical report titled '{title}'.
# SUB-CHAPTERS TO COVER: {subs_str}
# TARGET LENGTH: {target_words} words. (Provide clear, concise, and structured technical detail).

# QUALITY RULES:
# 1. Provide highly detailed, data-driven technical insights. DO NOT write shallow summaries.
# 2. The output MUST be a JSON list of objects. DO NOT output a flat list of strings.
# 3. For EACH object, your `sub_title` must have the hierarchical number (e.g., if the chapter is '3. Methodology', your sub_titles must be '3.1 [Topic]', '3.2 [Topic]', etc.).
# 4. For EACH object, the `content` field must contain a RICH BULLETED LIST of the technical findings. Write 2-4 sentences of deep technical analysis per bullet point.
# 5. Use the standard bullet character '• ' for each point inside the `content` string, and separate points with a double newline (\\n\\n).
# 6. You MUST GENERATE AN ARRAY OF MULTIPLE JSON OBJECTS (e.g., 4 to 5 objects). Create one isolated JSON object for EACH sub-chapter in 'SUB-CHAPTERS TO COVER'.
# 7. Your goal is approximately {target_words} words total across all subheadings for this chapter. 

# CRITICAL OUTPUT JSON FORMAT:
# [
#     {{ 
#         "sub_title": "X.1 First Sub-Chapter", 
#         "content": "• Point 1: Granular technical detail...\\n\\n• Point 2: Granular technical detail..." 
#     }},
#     {{ 
#         "sub_title": "X.2 Second Sub-Chapter", 
#         "content": "• Point 1: Granular technical detail...\\n\\n• Point 2: Granular technical detail..." 
#     }},
#     ...
# ]
# """.strip()

#     def build_prompt(self, title: str, project_type: str, description: str, pages: int) -> str:
#         """
#         Convert user input into a structured technical report instruction.
#         """
#         # Calculate target word density
#         total_target_words = pages * 400
#         words_per_section_avg = total_target_words // 9
        
#         prompt = f"""
# You are an expert technical report writer. Generate a comprehensive {project_type} report.

# TITLE: {title}
# PROJECT TYPE: {project_type}
# DESCRIPTION: {description}
# TARGET LENGTH: {pages} pages (Must reach approx. {total_target_words} words total)

# ### REQUIRED NESTED STRUCTURE EXAMPLE (STRICT JSON ONLY):
# For every major section, use this list-of-objects structure:
# "introduction": [
#     {{"sub_title": "1.1 Project Overview", "content": "3-4 detailed paragraphs discussing X, Y, and Z..."}},
#     {{"sub_title": "1.2 Necessity and Motivation", "content": "3-4 detailed paragraphs discussing A, B, and C..."}}
# ]

# ### JSON SCHEMA TO FOLLOW:
# {{
#     "abstract": "Minimum 250 words summary",
#     "introduction": [..nested subsections..],
#     "problem_statement": [..nested subsections..],
#     "objectives": ["Primary...", "Secondary...", "Technical..."],
#     "methodology": [..nested subsections..],
#     "tools_technologies": ["Tool A", "Tool B", "Env C"],
#     "system_architecture": [..nested subsections..],
#     "implementation": [..nested subsections..],
#     "results_analysis": [..nested subsections..],
#     "conclusion": [..nested subsections..],
#     "future_scope": [..nested subsections..]
# }}

# ### CRITICAL RULES:
# 1. Every section (except Abstract, Objectives, Tools) MUST be a list of objects with "sub_title" and "content".
# 2. Strings are FORBIDDEN for major section values. 
# 3. Each subsection content must be expansive and technically deep.
# 4. Target a total of {total_target_words} words. 
# 5. Return ONLY valid JSON. Keep the response long.
# """
#         return prompt.strip()

from typing import Dict, Any

class PromptBuilder:
    """
    Builds structured prompts for the LLM to generate technical report content.
    """
    
    def build_outline_prompt(self, title: str, project_type: str, description: str, pages: int) -> str:
        return f"""
Act as a Technical Architect. Create an 8-chapter outline for a {pages}-page report on '{title}'.
PROJECT: {project_type} | DESCRIPTION: {description}

TASK: Return a JSON object with these EXACT keys:
[introduction, problem_statement, methodology, system_architecture, implementation, results_analysis, future_scope, conclusion]

CRITICAL RULES:
- Generate EXACTLY 5 subsections per chapter.
- Do NOT generate fewer or more.

OUTPUT (JSON ONLY):
{{
    "abstract_plan": "Summary...",
    "sections": [
        {{ "title": "1. ...", "key": "introduction", "subsections": ["A","B","C","D","E"] }},
        {{ "title": "2. ...", "key": "problem_statement", "subsections": ["A","B","C","D","E"] }}
    ]
}}
""".strip()

    def build_section_prompt(self, title: str, section_title: str, subsections: list, target_words: int, chapter_number: int) -> str:
        subs_str = ", ".join(subsections)
        count = len(subsections)

        return f"""
Write chapter '{section_title}' for report '{title}'.

SUBSECTIONS: {subs_str}
TARGET WORDS: {target_words}

STRICT RULES:
1. Generate EXACTLY {count} objects.
2. Follow numbering:
   {chapter_number}.1 → {chapter_number}.{count}
3. One subsection = one object.
4. DO NOT skip or merge.

OUTPUT JSON:
[
    {{
        "sub_title": "{chapter_number}.1 {subsections[0] if count else 'Subsection'}",
        "content": "• Point 1...\\n\\n• Point 2..."
    }}
]
""".strip()

    def build_prompt(self, title: str, project_type: str, description: str, pages: int) -> str:
        total_target_words = pages * 400

        return f"""
Generate a {project_type} report.

TITLE: {title}
DESCRIPTION: {description}
TARGET: {total_target_words} words

RULES:
- Each section MUST have 5 subsections
- Use numbering 1.1 → 8.5
- Output ONLY JSON
"""