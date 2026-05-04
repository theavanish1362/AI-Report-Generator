from typing import Any, Dict


class PromptBuilder:
    """
    Builds prompts that fill the canonical 11-chapter report structure.

    The structure (chapters + subsections) is fixed by `CANONICAL_OUTLINE`;
    the LLM is responsible for producing typed content blocks for each
    canonical subsection slot. The caller assembles the final document.
    """

    BLOCK_FORMAT_GUIDE = """
CONTENT BLOCK TYPES
Each subsection's content is an array of blocks. Each block must be one of:
  - {"type": "paragraph", "text": "Free-form prose..."}
  - {"type": "ordered_list", "items": ["First step", "Second step", "Third step"]}
  - {"type": "unordered_list", "items": ["Point A", "Point B", "Point C"]}

WHEN TO USE EACH BLOCK TYPE
  - Use "paragraph" for narrative, explanations, definitions, justifications
    that don't decompose into discrete items.
  - Use "ordered_list" when items have an inherent order or sequence
    (steps, phases, ranked priorities, numbered requirements).
  - Use "unordered_list" for sets of features, characteristics, technologies,
    requirements, components, advantages, etc., where order does not matter.
  - You MAY combine multiple blocks in a subsection (e.g. an intro paragraph,
    then an unordered list, then a closing paragraph).

DO use list blocks for inherently list-like sections:
  - Functional / non-functional / hardware / software requirements
  - Tech stack and technology justifications
  - Core features, key modules, user types, assumptions, constraints
  - Test cases, output screens, references, deployment links
""".strip()

    def build_chapter_prompt(
        self,
        title: str,
        project_type: str,
        description: str,
        chapter: Dict[str, Any],
        target_words: int,
    ) -> str:
        subs = chapter["subsections"]
        sub_count = len(subs)
        words_per_sub = max(50, target_words // max(sub_count, 1))
        max_words_per_sub = int(words_per_sub * 1.15)

        sub_block_lines = [
            f"  - {s['number']} {s['title']} — {s.get('guidance', '').strip()}"
            for s in subs
        ]
        sub_block = "\n".join(sub_block_lines)

        keys_block = ", ".join(f'"{s["number"]}"' for s in subs)
        first = subs[0]
        example_pairs_lines = []
        for i, s in enumerate(subs):
            if i == 0:
                example_pairs_lines.append(
                    f'    "{s["number"]}": [\n'
                    f'        {{"type": "paragraph", "text": "Detailed prose for {s["title"]}..."}},\n'
                    f'        {{"type": "unordered_list", "items": ["First point", "Second point"]}}\n'
                    f'    ]'
                )
            else:
                example_pairs_lines.append(
                    f'    "{s["number"]}": [\n'
                    f'        {{"type": "paragraph", "text": "..."}}\n'
                    f'    ]'
                )
        example_pairs = ",\n".join(example_pairs_lines)

        return f"""
You are writing Chapter {chapter['number']} ("{chapter['title']}") of a {project_type}
technical report.

PROJECT TITLE: {title}
PROJECT DESCRIPTION:
{description}

CHAPTER PURPOSE: {chapter.get('guidance', '').strip()}

You MUST write content for each of the following {sub_count} subsections,
in this exact order. Do not skip, merge, rename, renumber, or add subsections.

{sub_block}

{self.BLOCK_FORMAT_GUIDE}

WRITING RULES
1. Each subsection MUST total {words_per_sub} (+/-10%) words across all its blocks.
   NEVER exceed {max_words_per_sub} words for any single subsection.
   The chapter as a whole should total ~{target_words} words.
2. Make the content technical, specific, and grounded in the PROJECT DESCRIPTION above.
3. Do NOT include the subsection number or title inside any block — the title
   is rendered separately.
4. Do NOT wrap the response in markdown, code fences, or commentary.

OUTPUT FORMAT
Return ONE JSON object whose keys are EXACTLY: {keys_block}.
Each value is an ARRAY of one or more block objects.

Example shape (you MUST adapt the block types to fit each subsection's content):
{{
{example_pairs}
}}
""".strip()

    def build_abstract_prompt(self, title: str, project_type: str, description: str) -> str:
        return f"""
Write a 220-260 word abstract for a {project_type} technical report titled
"{title}".

PROJECT DESCRIPTION:
{description}

The abstract MUST cover, in order: motivation, problem, proposed solution,
methodology, key results, and significance. Use a single coherent paragraph,
no bullet points.

Return ONE JSON object with this exact shape:
{{ "abstract": "..." }}
""".strip()
