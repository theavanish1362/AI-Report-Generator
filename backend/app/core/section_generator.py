# # ai-report-generator/backend/app/core/section_generator.py
# import logging
# import json
# from typing import Dict, Any, List, Optional, Callable, Awaitable
# from app.core.llm_client import LLMClient
# from app.core.prompt_builder import PromptBuilder
# from app.models.report_schema import ReportRequest

# logger = logging.getLogger(__name__)

# class SectionGenerator:
#     """
#     Orchestrates the multi-stage generation of long technical reports.
#     """
    
#     def __init__(self, progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None):
#         self.llm_client = LLMClient()
#         self.prompt_builder = PromptBuilder()
#         self.semaphore = None
#         self.progress_callback = progress_callback
#         self.progress_lock = None
#         self.chapter_states: Dict[int, Dict[str, Any]] = {}

#     @staticmethod
#     def _now_iso() -> str:
#         from datetime import datetime, timezone
#         return datetime.now(timezone.utc).isoformat()

#     def _chapter_snapshot_locked(self) -> List[Dict[str, Any]]:
#         return [dict(self.chapter_states[idx]) for idx in sorted(self.chapter_states.keys())]

#     async def _initialize_chapter_states(self, chapter_list: List[str]) -> List[Dict[str, Any]]:
#         import asyncio
#         if self.progress_lock is None:
#             self.progress_lock = asyncio.Lock()

#         async with self.progress_lock:
#             self.chapter_states = {}
#             for idx, title in enumerate(chapter_list, start=1):
#                 self.chapter_states[idx] = {
#                     "chapter_number": idx,
#                     "title": title,
#                     "status": "pending",
#                     "attempt": 0,
#                     "detail": "Waiting in queue",
#                     "updated_at": self._now_iso(),
#                 }
#             return self._chapter_snapshot_locked()

#     async def _update_chapter_state(
#         self,
#         chapter_number: int,
#         chapter_title: str,
#         status: str,
#         detail: str,
#         attempt: Optional[int] = None,
#     ) -> List[Dict[str, Any]]:
#         import asyncio
#         if self.progress_lock is None:
#             self.progress_lock = asyncio.Lock()

#         async with self.progress_lock:
#             chapter = self.chapter_states.get(
#                 chapter_number,
#                 {
#                     "chapter_number": chapter_number,
#                     "title": chapter_title,
#                     "status": "pending",
#                     "attempt": 0,
#                     "detail": "",
#                     "updated_at": self._now_iso(),
#                 },
#             )
#             chapter["title"] = chapter_title
#             chapter["status"] = status
#             chapter["detail"] = detail
#             if attempt is not None:
#                 chapter["attempt"] = attempt
#             chapter["updated_at"] = self._now_iso()
#             self.chapter_states[chapter_number] = chapter
#             return self._chapter_snapshot_locked()

#     async def _emit_progress(self, payload: Dict[str, Any]) -> None:
#         if not self.progress_callback:
#             return
#         try:
#             await self.progress_callback(payload)
#         except Exception as callback_error:
#             logger.warning("Progress callback failed: %s", callback_error)

#     async def _mark_chapter_completed(
#         self,
#         chapter_number: int,
#         chapter_title: str,
#         total: int,
#         chapter_details: Optional[List[Dict[str, Any]]] = None,
#     ) -> None:
#         import asyncio

#         if self.progress_lock is None:
#             self.progress_lock = asyncio.Lock()

#         async with self.progress_lock:
#             self.completed_sections += 1
#             completed = self.completed_sections

#         progress = 40 + int((completed / max(total, 1)) * 45)
#         if progress > 85:
#             progress = 85

#         await self._emit_progress(
#             {
#                 "phase": "chapter_generation",
#                 "message": f"Completed chapter {chapter_number}/{total}: {chapter_title}",
#                 "progress": progress,
#                 "current_chapter": chapter_number,
#                 "completed_chapters": completed,
#                 "total_chapters": total,
#                 "chapter_details": chapter_details if chapter_details is not None else [],
#             }
#         )

#     def _heal_keys(self, content: Dict[str, Any]) -> Dict[str, Any]:
#         """Maps common AI key variations back to the expected PDF schema."""
#         mapping = {
#             "intro": "introduction",
#             "executive_summary": "introduction",
#             "summary": "introduction",
#             "problem": "problem_statement",
#             "background": "problem_statement",
#             "goals": "objectives",
#             "stack": "tools_technologies",
#             "tech": "tools_technologies",
#             "architecture": "system_architecture",
#             "design": "system_architecture",
#             "logic": "implementation",
#             "testing": "results_analysis",
#             "benchmarks": "results_analysis",
#             "analysis": "results_analysis",
#             "roadmap": "future_scope",
#             "next_steps": "future_scope",
#             "final_thoughts": "conclusion"
#         }
        
#         healed = {}
#         for k, v in content.items():
#             new_key = mapping.get(k.lower(), k)
#             healed[new_key] = v
#         return healed

#     async def _generate_section(self, i: int, total: int, request: ReportRequest, section: Dict[str, Any], target_words: int) -> tuple:
#         """Helper to generate a single section with retry logic and concurrency limits."""
#         async with self.semaphore:
#             sec_title = section.get("title")
#             sec_key = section.get("key")
#             subsections = section.get("subsections", [])
#             chapter_number = i + 1
            
#             print(f"[PROGRESS] Starting Chapter {chapter_number}/{total}: '{sec_title}'...", flush=True)
            
#             # Map chapter keys to specific phases for conclusion/abstract
#             phase = f"generating_chapter_{chapter_number}"
#             if sec_key == "abstract": phase = "generating_abstract"
#             if sec_key == "conclusion": phase = "generating_conclusion"

#             await self._emit_progress(
#                 {
#                     "phase": phase,
#                     "message": f"Generating {sec_title}",
#                     "progress": 40 + int((i / max(total, 1)) * 45),
#                     "current_chapter": chapter_number,
#                     "chapter_title": sec_title,
#                     "total_chapters": total,
#                     "sub_steps": ["Analyzing components...", "Writing introduction...", "Structuring content..."]
#                 }
#             )
            
#             sec_prompt = self.prompt_builder.build_section_prompt(
#                 title=request.title,
#                 section_title=sec_title,
#                 subsections=subsections,
#                 target_words=target_words,
#                 chapter_number=chapter_number
#             )
            
#             # Retry loop for stability
#             max_retries = 2
#             for attempt in range(max_retries + 1):
#                 try:
#                     chapter_details = await self._update_chapter_state(
#                         chapter_number=chapter_number,
#                         chapter_title=sec_title,
#                         status="running",
#                         detail=f"Generating content (attempt {attempt + 1}/{max_retries + 1})",
#                         attempt=attempt + 1,
#                     )
#                     phase = f"generating_chapter_{chapter_number}"
#                     if sec_key == "abstract": phase = "generating_abstract"
#                     if sec_key == "conclusion": phase = "generating_conclusion"

#                     await self._emit_progress(
#                         {
#                             "phase": phase,
#                             "message": f"Generating {sec_title} (attempt {attempt + 1})",
#                             "progress": 40 + int((i / max(total, 1)) * 45),
#                             "current_chapter": chapter_number,
#                             "total_chapters": total,
#                             "chapter_details": chapter_details,
#                             "sub_steps": ["Refining content...", "Optimizing structure...", "Verifying technical accuracy..."]
#                         }
#                     )

#                     chapter_data = await self.llm_client.generate_content(sec_prompt)
                    
#                     # SMART UNWRAPPING: Handle if model wrapped list in a dict
#                     if isinstance(chapter_data, dict):
#                         # 1. Look for any list inside the dict (common LLM behavior)
#                         for val in chapter_data.values():
#                             if isinstance(val, list):
#                                 chapter_data = val
#                                 break
                        
#                         # 2. If it's still a dict, it might be the content itself
#                         if isinstance(chapter_data, dict):
#                             # Check if the dict is already a single subsection object
#                             if "sub_title" in chapter_data and "content" in chapter_data:
#                                 chapter_data = [chapter_data]
#                             elif "title" in chapter_data and "content" in chapter_data:
#                                 chapter_data = [{"sub_title": chapter_data["title"], "content": chapter_data["content"]}]
#                             else:
#                                 # Convert dict to a single-item list fallback
#                                 chapter_data = [{"sub_title": "Section Details", "content": str(chapter_data)}]
                    
#                     # 3. Handle flat string output
#                     if isinstance(chapter_data, str):
#                         chapter_data = [{"sub_title": "Executive Overview", "content": chapter_data}]

#                     if isinstance(chapter_data, list):
#                         print(f"[SUCCESS] Chapter {chapter_number} complete: '{sec_title}'", flush=True)
#                         chapter_details = await self._update_chapter_state(
#                             chapter_number=chapter_number,
#                             chapter_title=sec_title,
#                             status="completed",
#                             detail=f"Chapter generated successfully on attempt {attempt + 1}",
#                             attempt=attempt + 1,
#                         )
#                         await self._mark_chapter_completed(chapter_number, sec_title, total, chapter_details=chapter_details)
#                         return sec_key, chapter_data
                        
#                     # Final fallback for anything else
#                     chapter_details = await self._update_chapter_state(
#                         chapter_number=chapter_number,
#                         chapter_title=sec_title,
#                         status="fallback",
#                         detail=f"Used fallback parsing on attempt {attempt + 1}",
#                         attempt=attempt + 1,
#                     )
#                     await self._mark_chapter_completed(chapter_number, sec_title, total, chapter_details=chapter_details)
#                     return sec_key, [{"sub_title": "Overview", "content": str(chapter_data)}]
                    
#                 except Exception as e:
#                     if attempt < max_retries:
#                         print(f"[RETRY] Attempt {attempt+1} for '{sec_title}' due to: {e}", flush=True)
#                         chapter_details = await self._update_chapter_state(
#                             chapter_number=chapter_number,
#                             chapter_title=sec_title,
#                             status="retrying",
#                             detail=f"Retrying due to: {str(e)[:120]}",
#                             attempt=attempt + 1,
#                         )
#                         await self._emit_progress(
#                             {
#                                 "phase": f"generating_chapter_{chapter_number}",
#                                 "message": f"Retrying {sec_title}",
#                                 "progress": 40 + int((i / max(total, 1)) * 45),
#                                 "current_chapter": chapter_number,
#                                 "total_chapters": total,
#                                 "chapter_details": chapter_details,
#                                 "sub_steps": ["Retrying generation...", f"Error: {str(e)[:50]}"]
#                             }
#                         )
#                         continue
#                     else:
#                         print(f"[ERROR] Chapter '{sec_title}' failed after retries: {e}", flush=True)
#                         chapter_details = await self._update_chapter_state(
#                             chapter_number=chapter_number,
#                             chapter_title=sec_title,
#                             status="fallback",
#                             detail=f"Failed after retries. Using fallback content: {str(e)[:120]}",
#                             attempt=attempt + 1,
#                         )
#                         await self._mark_chapter_completed(chapter_number, sec_title, total, chapter_details=chapter_details)
#                         return sec_key, [{"sub_title": "Outcome", "content": f"Content unavailable: {e}"}]

#     async def generate_full_report(self, request: ReportRequest) -> Dict[str, Any]:
#         """
#         Main entry point for Turbo multi-stage generation.
#         """
#         import asyncio
#         from datetime import datetime
#         if self.semaphore is None:
#             self.semaphore = asyncio.Semaphore(5)
#         if self.progress_lock is None:
#             self.progress_lock = asyncio.Lock()
#         self.completed_sections = 0

#         print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [INIT] Starting Turbo Generation for '{request.title}'", flush=True)
        
#         # Phase 1: Try AI Outline with a strict 45s timeout
#         try:
#             await self._emit_progress(
#                 {
#                     "phase": "generating_outline",
#                     "message": "Generating report outline",
#                     "progress": 30,
#                 }
#             )
#             outline_prompt = self.prompt_builder.build_outline_prompt(
#                 title=request.title, project_type=request.project_type,
#                 description=request.description, pages=request.pages
#             )
#             print(f"[{datetime.now().strftime('%H:%M:%S')}] [PHASE 1] Requesting AI Outline (45s timeout)...", flush=True)
            
#             # Using wait_for to prevent infinite hanging
#             outline = await asyncio.wait_for(self.llm_client.generate_content(outline_prompt), timeout=300.0)
#             print(f"[{datetime.now().strftime('%H:%M:%S')}] [PHASE 1] AI Outline received successfully.", flush=True)
            
#         except (asyncio.TimeoutError, Exception) as e:
#             print(f"[{datetime.now().strftime('%H:%M:%S')}] [PHASE 1] AI Outline hung or failed. Switching to High-Quality Master Template...", flush=True)
#             # HIGH QUALITY FALLBACK: Ensuring we never stick at Phase 1
#             outline = {
#                 "title": request.title,
#                 "abstract_plan": f"A comprehensive technical analysis and strategic roadmap for {request.title}.",
#                 "sections": [
#                     { "title": "1. Executive Summary and Strategic Context", "key": "introduction", "subsections": ["Industry Landscape & Trends", "Project Necessity and Motivation", "Strategic Value Proposition", "Long-term Vision & Scalability", "Operational Scope"] },
#                     { "title": "2. Technical Foundation and Requirements", "key": "problem_statement", "subsections": ["Core Problem Definition", "Functional User Requirements", "Non-Functional Technical Constraints", "Compliance & Regulatory Standards", "Stakeholder Impact Analysis"] },
#                     { "title": "3. Proposed Methodology and Framework", "key": "methodology", "subsections": ["Strategic Methodology Selection", "Development Life Cycle Model", "Feasibility and Risk Assessment", "Alternative Solutions Analysis", "Research Foundations"] },
#                     { "title": "4. Advanced System Architecture and Design", "key": "system_architecture", "subsections": ["High-Level Structural Overview", "Modular Component Interaction", "Data Security and Flow Design", "Asynchronous Messaging Patterns", "Fault Tolerance Design"] },
#                     { "title": "5. Implementation Logic and Process Flow", "key": "implementation", "subsections": ["Core Development Frameworks", "API Integration Strategy", "Business Logic Orchestration", "Security & Identity Management", "Quality Assurance Protocols"] },
#                     { "title": "6. Empirical Performance and Results", "key": "results_analysis", "subsections": ["Benchmarking and Technical KPIs", "Critical Analysis of Outcomes", "Efficiency & Latency Evaluation", "Scalability Stress Testing", "Optimization Reports"] },
#                     { "title": "7. Strategic Future Scope and Evolution", "key": "future_scope", "subsections": ["Emerging Tech Integration Pipeline", "Long-term Scalability Roadmap", "Market Competitiveness Strategy", "Post-Deployment Lifecycle", "Innovation Vectors"] },
#                     { "title": "8. Conclusion and Strategic Synthesis", "key": "conclusion", "subsections": ["Final Technical Synthesis", "Strategic Final Recommendations", "Critical Project Evaluation", "Closing Executive Remarks"] }
#                 ]
#             }

#         # Phase 2: Parallel Generation
#         try:
#             print(f"[{datetime.now().strftime('%H:%M:%S')}] [PHASE 2] Starting Parallel Generation (Turbo)...", flush=True)
            
#             final_content = {
#                 "title": request.title,
#                 "project_type": request.project_type,
#                 "abstract": outline.get("abstract_plan", "Introduction to " + request.title),
#                 "objectives": [],
#                 "tools_technologies": [],
#                 "image_prompts": []
#             }
            
#             sections = outline.get("sections", [])
#             total_sections = len(sections)
#             chapter_list = [sec.get("title", f"Chapter {idx + 1}") for idx, sec in enumerate(sections)]
#             chapter_details = await self._initialize_chapter_states(chapter_list)
#             await self._emit_progress(
#                 {
#                     "phase": "outline_generated",
#                     "message": "Outline generated. Starting chapter generation",
#                     "progress": 40,
#                     "chapter_list": chapter_list,
#                     "total_chapters": total_sections,
#                     "completed_chapters": 0,
#                     "chapter_details": chapter_details,
#                 }
#             )
#             words_per = (request.pages * 400) // max(total_sections, 1)
            
#             tasks = [
#                 self._generate_section(i, total_sections, request, sec, words_per)
#                 for i, sec in enumerate(sections)
#             ]
            
#             results = await asyncio.gather(*tasks)
            
#             for sec_key, chapter_data in results:
#                 final_content[sec_key] = chapter_data
            
#             # Apply key healing to align AI output with PDF schema
#             final_content = self._heal_keys(final_content)
                
#             print(f"[{datetime.now().strftime('%H:%M:%S')}] [FINISH] All chapters combined successfully!", flush=True)
#             return final_content
#         except Exception as e:
#             print(f"[{datetime.now().strftime('%H:%M:%S')}] [CRITICAL] Generation flow crashed: {e}", flush=True)
#             raise e


import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from app.core.llm_client import LLMClient
from app.core.prompt_builder import PromptBuilder
from app.models.report_schema import ReportRequest

logger = logging.getLogger(__name__)

class SectionGenerator:
    
    def __init__(self, progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None):
        self.llm_client = LLMClient()
        self.prompt_builder = PromptBuilder()
        self.semaphore = None
        self.progress_callback = progress_callback
        self.progress_lock = None
        self.chapter_states: Dict[int, Dict[str, Any]] = {}

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    async def _emit_progress(self, payload: Dict[str, Any]) -> None:
        if not self.progress_callback:
            return
        try:
            await self.progress_callback(payload)
        except Exception as e:
            logger.warning("Progress callback failed: %s", e)

    # ===========================
    # ✅ FIXED VALIDATION BLOCK
    # ===========================
    def _validate_chapter_data(self, chapter_data, chapter_number):
        if isinstance(chapter_data, dict):
            # Aggressive unwrapping for Llama 8B over-formatting
            if "report" in chapter_data and isinstance(chapter_data["report"], dict):
                chapter_data = chapter_data["report"]
                
            if "content" in chapter_data and isinstance(chapter_data["content"], list):
                chapter_data = chapter_data["content"]
            elif "sections" in chapter_data and isinstance(chapter_data["sections"], list):
                chapter_data = chapter_data["sections"]
            elif "sub_title" in chapter_data and "content" in chapter_data:
                chapter_data = [chapter_data]
            elif "title" in chapter_data and "content" in chapter_data:
                chapter_data = [{"sub_title": chapter_data["title"], "content": chapter_data["content"]}]
            else:
                # Blindly search for the first available list in the dictionary
                for v in chapter_data.values():
                    if isinstance(v, list):
                        chapter_data = v
                        break
        
        if not isinstance(chapter_data, list):
            print(f"[WARNING] Invalid format. Forcing list.", flush=True)
            chapter_data = [{
                "sub_title": f"{chapter_number}.1 Overview",
                "content": str(chapter_data)
            }]

        validated = []
        for idx, item in enumerate(chapter_data):
            if isinstance(item, dict) and "sub_title" in item and "content" in item:
                validated.append(item)
            else:
                validated.append({
                    "sub_title": f"{chapter_number}.{idx+1}",
                    "content": str(item)
                })

        return validated

    async def _generate_section(self, i, total, request, section, target_words):
        async with self.semaphore:
            sec_title = section.get("title")
            sec_key = section.get("key")
            subsections = section.get("subsections", [])
            chapter_number = i + 1

            print(f"[START] Chapter {chapter_number}: {sec_title}", flush=True)

            prompt = self.prompt_builder.build_section_prompt(
                title=request.title,
                section_title=sec_title,
                subsections=subsections,
                target_words=target_words,
                chapter_number=chapter_number
            )

            try:
                chapter_data = await self.llm_client.generate_content(prompt)

                # ✅ APPLY STRICT VALIDATION
                chapter_data = self._validate_chapter_data(chapter_data, chapter_number)

                print(f"[SUCCESS] Chapter {chapter_number} generated", flush=True)

                return sec_key, chapter_data

            except Exception as e:
                print(f"[ERROR] Chapter {chapter_number}: {e}", flush=True)
                return sec_key, [{
                    "sub_title": f"{chapter_number}.1 Error",
                    "content": str(e)
                }]

    def _heal_keys(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Maps common AI key variations back to the expected PDF schema."""
        mapping = {
            "intro": "introduction",
            "executive_summary": "introduction",
            "summary": "introduction",
            "problem": "problem_statement",
            "background": "problem_statement",
            "goals": "objectives",
            "stack": "tools_technologies",
            "tech": "tools_technologies",
            "architecture": "system_architecture",
            "design": "system_architecture",
            "logic": "implementation",
            "testing": "results_analysis",
            "benchmarks": "results_analysis",
            "analysis": "results_analysis",
            "roadmap": "future_scope",
            "next_steps": "future_scope",
            "final_thoughts": "conclusion"
        }
        healed = {}
        for k, v in content.items():
            healed[mapping.get(k.lower(), k)] = v
        return healed

    async def generate_full_report(self, request: ReportRequest) -> Dict[str, Any]:
        import asyncio
        from datetime import datetime

        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(5)

        print(f"[INIT] Generating report: {request.title}", flush=True)

        # ===========================
        # PHASE 1: OUTLINE
        # ===========================
        try:
            outline_prompt = self.prompt_builder.build_outline_prompt(
                title=request.title,
                project_type=request.project_type,
                description=request.description,
                pages=request.pages
            )

            outline = await self.llm_client.generate_content(outline_prompt)

        except Exception:
            print("[FALLBACK] Using default outline", flush=True)

            outline = {
                "sections": [
                    { "title": "1. Introduction", "key": "introduction",
                      "subsections": ["Overview", "Motivation", "Scope", "Challenges", "Summary"] },

                    { "title": "2. Problem Statement", "key": "problem_statement",
                      "subsections": ["Definition", "Requirements", "Constraints", "Stakeholders", "Impact"] },

                    { "title": "3. Methodology", "key": "methodology",
                      "subsections": ["Approach", "Model", "Feasibility", "Alternatives", "Research"] },

                    { "title": "4. System Architecture", "key": "system_architecture",
                      "subsections": ["Overview", "Components", "Data Flow", "Security", "Scalability"] },

                    { "title": "5. Implementation", "key": "implementation",
                      "subsections": ["Tools", "API", "Logic", "Security", "Testing"] },

                    { "title": "6. Results Analysis", "key": "results_analysis",
                      "subsections": ["Metrics", "Evaluation", "Performance", "Scalability", "Optimization"] },

                    { "title": "7. Future Scope", "key": "future_scope",
                      "subsections": ["Enhancements", "Scaling", "Innovation", "Maintenance", "Trends"] },

                    { "title": "8. Conclusion", "key": "conclusion",
                      "subsections": ["Summary", "Findings", "Evaluation", "Recommendations", "Closure"] }
                ]
            }

        # ===========================
        # PHASE 2: GENERATION
        # ===========================
        sections = outline.get("sections", [])
        total = len(sections)

        words_per_section = (request.pages * 400) // max(total, 1)

        tasks = [
            self._generate_section(i, total, request, sec, words_per_section)
            for i, sec in enumerate(sections)
        ]

        results = await asyncio.gather(*tasks)

        final_content = {
            "title": request.title,
            "project_type": request.project_type,
            "abstract": request.description,
            "objectives": ["Primary objective of " + request.title, "Secondary requirement fulfillment", "Technical scope validation"],
            "tools_technologies": ["Chosen frameworks", "Deployment environment", "Core utilities"],
        }

        for key, data in results:
            final_content[key] = data

        final_content = self._heal_keys(final_content)

        print("[DONE] Report generation complete", flush=True)

        return final_content