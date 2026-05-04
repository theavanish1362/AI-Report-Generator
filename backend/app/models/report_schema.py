from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class ReportRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    project_type: str = Field(..., description="academic | industrial")
    description: str = Field(..., min_length=10, max_length=5000)
    # Minimum 18 = structural floor of the canonical 11-chapter layout
    # (cover + TOC + abstract + 11 chapters, each with H2 subsection headings).
    # See pagination constants in section_generator.
    pages: int = Field(20, ge=18, le=40)

    @field_validator("project_type")
    @classmethod
    def validate_project_type(cls, v: str) -> str:
        if v.lower() not in {"academic", "industrial"}:
            raise ValueError('project_type must be either "academic" or "industrial"')
        return v.lower()


class ReportResponse(BaseModel):
    success: bool
    message: str
    pdf_path: Optional[str] = None
    report_id: Optional[str] = None
    error_details: Optional[str] = None


class ChartData(BaseModel):
    type: str
    title: str
    data: Dict[str, Any]

    @field_validator("type")
    @classmethod
    def validate_chart_type(cls, v: str) -> str:
        if v not in {"bar", "line", "pie", "scatter"}:
            raise ValueError("Unsupported chart type")
        return v


class ParagraphBlock(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: str = Field(..., min_length=1)


class OrderedListBlock(BaseModel):
    type: Literal["ordered_list"] = "ordered_list"
    items: List[str] = Field(..., min_length=1)

    @field_validator("items")
    @classmethod
    def items_must_be_non_empty(cls, v: List[str]) -> List[str]:
        cleaned = [item.strip() for item in v if item and item.strip()]
        if not cleaned:
            raise ValueError("ordered_list must contain at least one non-empty item")
        return cleaned


class UnorderedListBlock(BaseModel):
    type: Literal["unordered_list"] = "unordered_list"
    items: List[str] = Field(..., min_length=1)

    @field_validator("items")
    @classmethod
    def items_must_be_non_empty(cls, v: List[str]) -> List[str]:
        cleaned = [item.strip() for item in v if item and item.strip()]
        if not cleaned:
            raise ValueError("unordered_list must contain at least one non-empty item")
        return cleaned


ContentBlock = Annotated[
    Union[ParagraphBlock, OrderedListBlock, UnorderedListBlock],
    Field(discriminator="type"),
]


class Subsection(BaseModel):
    number: str
    title: str
    blocks: List[ContentBlock] = Field(..., min_length=1)


class Chapter(BaseModel):
    number: int
    key: str
    title: str
    subsections: List[Subsection]


# ---------------------------------------------------------------------------
# CANONICAL REPORT OUTLINE
# ---------------------------------------------------------------------------
# This is the single source of truth for the report's structure. Every
# generated report MUST contain exactly these chapters and subsections, in
# this order. Both the prompt builder and the PDF renderer derive their
# behaviour from this list, and ReportContent rejects any document that
# does not match it.
# ---------------------------------------------------------------------------

CANONICAL_OUTLINE: List[Dict[str, Any]] = [
    {
        "number": 1,
        "key": "introduction",
        "title": "Introduction",
        "guidance": "Overview of the project: establish context, problem and proposed solution.",
        "subsections": [
            {
                "number": "1.1",
                "title": "Project Aim & Objectives",
                "guidance": "Clearly define what problem you are solving. State measurable goals (performance, usability, scalability).",
            },
            {
                "number": "1.2",
                "title": "Background of the Project",
                "guidance": "Context of the domain (e.g. job portal, CRM, AI system). Existing systems and their limitations.",
            },
            {
                "number": "1.3",
                "title": "Problem Statement",
                "guidance": "Real-world problem identified. Why current solutions are insufficient.",
            },
            {
                "number": "1.4",
                "title": "Proposed Solution",
                "guidance": "Approach and system idea. Key innovations or improvements over existing solutions.",
            },
            {
                "number": "1.5",
                "title": "Scope of the Project",
                "guidance": "Features included. Features explicitly NOT included (important academically).",
            },
            {
                "number": "1.6",
                "title": "Market Research / Competitive Analysis",
                "guidance": "Compare with relevant competing platforms. Highlight gaps your system solves.",
            },
        ],
    },
    {
        "number": 2,
        "key": "project_analysis",
        "title": "Project Analysis",
        "guidance": "Detailed analysis of the project's positioning, functions, users, assumptions and constraints.",
        "subsections": [
            {
                "number": "2.1",
                "title": "Product Perspective",
                "guidance": "Where the system fits (standalone product / integrated module / platform extension).",
            },
            {
                "number": "2.2",
                "title": "Product Functions",
                "guidance": "Core features (authentication, dashboard, CRUD, analytics, etc.).",
            },
            {
                "number": "2.3",
                "title": "User Characteristics",
                "guidance": "Types of users (admin, end user, etc.) and their needs.",
            },
            {
                "number": "2.4",
                "title": "Assumptions & Dependencies",
                "guidance": "Internet dependency, third-party APIs, expected runtime environment.",
            },
            {
                "number": "2.5",
                "title": "Constraints",
                "guidance": "Technical (hosting, performance) and business (budget, timeline) constraints.",
            },
        ],
    },
    {
        "number": 3,
        "key": "srs",
        "title": "Software Requirement Specification (SRS)",
        "guidance": "Formal specification of system requirements.",
        "subsections": [
            {
                "number": "3.1",
                "title": "General Description",
                "guidance": "System overview in simple terms.",
            },
            {
                "number": "3.2",
                "title": "Functional Requirements",
                "guidance": "What the system must do (e.g. user authentication, data management, API integration).",
            },
            {
                "number": "3.3",
                "title": "Non-Functional Requirements",
                "guidance": "Performance, security, scalability, reliability targets.",
            },
            {
                "number": "3.4",
                "title": "Hardware Requirements",
                "guidance": "Server specifications and client/device requirements.",
            },
            {
                "number": "3.5",
                "title": "Software Requirements",
                "guidance": "Tech stack used (e.g. React, Next.js, Node.js, MongoDB, PostgreSQL).",
            },
            {
                "number": "3.6",
                "title": "Technology Justification",
                "guidance": "Why each technology in the stack was chosen.",
            },
        ],
    },
    {
        "number": 4,
        "key": "system_design",
        "title": "System Design & Architecture",
        "guidance": "High-level and detailed system design.",
        "subsections": [
            {
                "number": "4.1",
                "title": "System Architecture",
                "guidance": "High-level architecture (frontend + backend + database). Describe layers and interactions.",
            },
            {
                "number": "4.2",
                "title": "Data Flow Diagram (DFD)",
                "guidance": "Describe Level 0 (context diagram), Level 1 and Level 2 data flows in text.",
            },
            {
                "number": "4.3",
                "title": "Database Design",
                "guidance": "ER design. Tables / collections, fields, and their relationships.",
            },
            {
                "number": "4.4",
                "title": "API Design",
                "guidance": "Endpoints, request/response structure, flow between services.",
            },
            {
                "number": "4.5",
                "title": "UI/UX Design",
                "guidance": "Wireframes / screens. Describe key user flows and interaction patterns.",
            },
        ],
    },
    {
        "number": 5,
        "key": "implementation",
        "title": "Implementation (Development Phase)",
        "guidance": "How the system was actually built.",
        "subsections": [
            {
                "number": "5.1",
                "title": "Frontend Implementation",
                "guidance": "Components, state management (Redux / Context), routing.",
            },
            {
                "number": "5.2",
                "title": "Backend Implementation",
                "guidance": "APIs, request handling, authentication (e.g. JWT flow).",
            },
            {
                "number": "5.3",
                "title": "Database Implementation",
                "guidance": "Concrete schema design, indexes, relationships, query patterns.",
            },
            {
                "number": "5.4",
                "title": "Key Modules",
                "guidance": "Authentication module, dashboard, reporting / analytics modules.",
            },
        ],
    },
    {
        "number": 6,
        "key": "testing",
        "title": "Testing & Quality Assurance",
        "guidance": "How quality was verified.",
        "subsections": [
            {
                "number": "6.1",
                "title": "Testing Strategy",
                "guidance": "Unit testing, integration testing, system testing.",
            },
            {
                "number": "6.2",
                "title": "Test Cases",
                "guidance": "Representative test cases with input and expected output.",
            },
            {
                "number": "6.3",
                "title": "Bug Tracking & Fixes",
                "guidance": "Notable issues encountered and how they were resolved.",
            },
            {
                "number": "6.4",
                "title": "Performance Testing",
                "guidance": "Load handling, response time, throughput observations.",
            },
        ],
    },
    {
        "number": 7,
        "key": "results_discussion",
        "title": "Results & Discussion",
        "guidance": "Concrete outcomes and analysis.",
        "subsections": [
            {
                "number": "7.1",
                "title": "Output Screens",
                "guidance": "Describe screenshots and key UI states the system produces.",
            },
            {
                "number": "7.2",
                "title": "Performance Analysis",
                "guidance": "Speed, efficiency, real-world numbers and benchmarks.",
            },
            {
                "number": "7.3",
                "title": "Comparison with Existing Systems",
                "guidance": "Improvements achieved over prior art and competing systems.",
            },
        ],
    },
    {
        "number": 8,
        "key": "challenges_learnings",
        "title": "Challenges & Learnings",
        "guidance": "Reflective section on obstacles and growth.",
        "subsections": [
            {
                "number": "8.1",
                "title": "Technical Challenges",
                "guidance": "Hardest engineering problems faced and how they were tackled.",
            },
            {
                "number": "8.2",
                "title": "Debugging Issues",
                "guidance": "Notable debugging episodes and their resolutions.",
            },
            {
                "number": "8.3",
                "title": "Deployment Issues",
                "guidance": "Pain points encountered when deploying and how they were resolved.",
            },
            {
                "number": "8.4",
                "title": "Learnings & Reflections",
                "guidance": "What was learned overall (important for viva).",
            },
        ],
    },
    {
        "number": 9,
        "key": "conclusion_future_scope",
        "title": "Conclusion & Future Scope",
        "guidance": "Wrap-up and forward-looking improvements.",
        "subsections": [
            {
                "number": "9.1",
                "title": "Project Summary & Success",
                "guidance": "Summary of project success against stated objectives.",
            },
            {
                "number": "9.2",
                "title": "Future Improvements",
                "guidance": "Future improvements (e.g. deeper AI integration, scaling, mobile app version).",
            },
        ],
    },
    {
        "number": 10,
        "key": "references",
        "title": "References",
        "guidance": "Academic references and resources used.",
        "subsections": [
            {
                "number": "10.1",
                "title": "Research Papers",
                "guidance": "Numbered list of relevant research papers / citations.",
            },
            {
                "number": "10.2",
                "title": "Documentation",
                "guidance": "Numbered list of official documentation resources referenced.",
            },
            {
                "number": "10.3",
                "title": "Tools Used",
                "guidance": "Numbered list of tools, libraries and frameworks relied on.",
            },
        ],
    },
    {
        "number": 11,
        "key": "appendices",
        "title": "Appendices",
        "guidance": "Supporting material that complements the main report.",
        "subsections": [
            {
                "number": "11.1",
                "title": "Code Snippets",
                "guidance": "Representative code excerpts for key flows.",
            },
            {
                "number": "11.2",
                "title": "API Responses",
                "guidance": "Sample API request / response payloads.",
            },
            {
                "number": "11.3",
                "title": "Project Timeline (Gantt)",
                "guidance": "Project milestones and timeline expressed in text form.",
            },
            {
                "number": "11.4",
                "title": "Deployment Links",
                "guidance": "Live demo URLs, repositories, deployment artefacts.",
            },
        ],
    },
]


def get_canonical_chapter(key: str) -> Optional[Dict[str, Any]]:
    for chapter in CANONICAL_OUTLINE:
        if chapter["key"] == key:
            return chapter
    return None


def get_canonical_chapter_keys() -> List[str]:
    return [c["key"] for c in CANONICAL_OUTLINE]


class ReportContent(BaseModel):
    """
    Strict report content model. The `chapters` field MUST mirror
    `CANONICAL_OUTLINE` exactly: same length, same chapter numbers and keys
    in the same order, and within each chapter the same subsection numbers
    in the same order.
    """

    title: str
    project_type: str
    abstract: str
    chapters: List[Chapter]

    @model_validator(mode="after")
    def validate_canonical_structure(self) -> "ReportContent":
        expected = CANONICAL_OUTLINE
        if len(self.chapters) != len(expected):
            raise ValueError(
                f"Expected {len(expected)} chapters, got {len(self.chapters)}"
            )

        for chapter, exp in zip(self.chapters, expected):
            if chapter.number != exp["number"]:
                raise ValueError(
                    f"Chapter order mismatch: expected number {exp['number']}, got {chapter.number}"
                )
            if chapter.key != exp["key"]:
                raise ValueError(
                    f"Chapter {chapter.number}: expected key '{exp['key']}', got '{chapter.key}'"
                )

            expected_subs = exp["subsections"]
            if len(chapter.subsections) != len(expected_subs):
                raise ValueError(
                    f"Chapter {chapter.number} ({chapter.key}): expected "
                    f"{len(expected_subs)} subsections, got {len(chapter.subsections)}"
                )

            for sub, exp_sub in zip(chapter.subsections, expected_subs):
                if sub.number != exp_sub["number"]:
                    raise ValueError(
                        f"Chapter {chapter.number}: expected subsection "
                        f"{exp_sub['number']}, got {sub.number}"
                    )

        return self
