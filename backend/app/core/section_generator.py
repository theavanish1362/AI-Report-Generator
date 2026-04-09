# ai-report-generator/backend/app/core/section_generator.py
import logging
import json
from typing import Dict, Any, List
from app.core.llm_client import LLMClient
from app.core.prompt_builder import PromptBuilder
from app.models.report_schema import ReportRequest

logger = logging.getLogger(__name__)

class SectionGenerator:
    """
    Orchestrates the multi-stage generation of long technical reports.
    """
    
    def __init__(self):
        self.llm_client = LLMClient()
        self.prompt_builder = PromptBuilder()
        self.semaphore = None

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
            new_key = mapping.get(k.lower(), k)
            healed[new_key] = v
        return healed

    async def _generate_section(self, i: int, total: int, request: ReportRequest, section: Dict[str, Any], target_words: int) -> tuple:
        """Helper to generate a single section with retry logic and concurrency limits."""
        async with self.semaphore:
            sec_title = section.get("title")
            sec_key = section.get("key")
            subsections = section.get("subsections", [])
            
            print(f"[PROGRESS] Starting Chapter {i+1}/{total}: '{sec_title}'...", flush=True)
            
            sec_prompt = self.prompt_builder.build_section_prompt(
                title=request.title,
                section_title=sec_title,
                subsections=subsections,
                target_words=target_words
            )
            
            # Retry loop for stability
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    chapter_data = await self.llm_client.generate_content(sec_prompt)
                    
                    # SMART UNWRAPPING: Handle if model wrapped list in a dict
                    if isinstance(chapter_data, dict):
                        # 1. Look for any list inside the dict (common LLM behavior)
                        for val in chapter_data.values():
                            if isinstance(val, list):
                                chapter_data = val
                                break
                        
                        # 2. If it's still a dict, it might be the content itself
                        if isinstance(chapter_data, dict):
                            # Convert dict to a single-item list
                            chapter_data = [{"sub_title": "Section Details", "content": str(chapter_data)}]
                    
                    # 3. Handle flat string output
                    if isinstance(chapter_data, str):
                        chapter_data = [{"sub_title": "Executive Overview", "content": chapter_data}]

                    if isinstance(chapter_data, list):
                        print(f"[SUCCESS] Chapter {i+1} complete: '{sec_title}'", flush=True)
                        return sec_key, chapter_data
                        
                    # Final fallback for anything else
                    return sec_key, [{"sub_title": "Overview", "content": str(chapter_data)}]
                    
                except Exception as e:
                    if attempt < max_retries:
                        print(f"[RETRY] Attempt {attempt+1} for '{sec_title}' due to: {e}", flush=True)
                        continue
                    else:
                        print(f"[ERROR] Chapter '{sec_title}' failed after retries: {e}", flush=True)
                        return sec_key, [{"sub_title": "Outcome", "content": f"Content unavailable: {e}"}]

    async def generate_full_report(self, request: ReportRequest) -> Dict[str, Any]:
        """
        Main entry point for Turbo multi-stage generation.
        """
        import asyncio
        from datetime import datetime
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(5)

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [INIT] Starting Turbo Generation for '{request.title}'", flush=True)
        
        # Phase 1: Try AI Outline with a strict 45s timeout
        try:
            outline_prompt = self.prompt_builder.build_outline_prompt(
                title=request.title, project_type=request.project_type,
                description=request.description, pages=request.pages
            )
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [PHASE 1] Requesting AI Outline (45s timeout)...", flush=True)
            
            # Using wait_for to prevent infinite hanging
            outline = await asyncio.wait_for(self.llm_client.generate_content(outline_prompt), timeout=90.0)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [PHASE 1] AI Outline received successfully.", flush=True)
            
        except (asyncio.TimeoutError, Exception) as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [PHASE 1] AI Outline hung or failed. Switching to High-Quality Master Template...", flush=True)
            # HIGH QUALITY FALLBACK: Ensuring we never stick at Phase 1
            outline = {
                "title": request.title,
                "abstract_plan": f"A comprehensive technical analysis and strategic roadmap for {request.title}.",
                "sections": [
                    { "title": "1. Executive Summary and Strategic Context", "key": "introduction", "subsections": ["Industry Landscape & Trends", "Project Necessity and Motivation", "Strategic Value Proposition", "Long-term Vision & Scalability", "Operational Scope"] },
                    { "title": "2. Technical Foundation and Requirements", "key": "problem_statement", "subsections": ["Core Problem Definition", "Functional User Requirements", "Non-Functional Technical Constraints", "Compliance & Regulatory Standards", "Stakeholder Impact Analysis"] },
                    { "title": "3. Proposed Methodology and Framework", "key": "methodology", "subsections": ["Strategic Methodology Selection", "Development Life Cycle Model", "Feasibility and Risk Assessment", "Alternative Solutions Analysis", "Research Foundations"] },
                    { "title": "4. Advanced System Architecture and Design", "key": "system_architecture", "subsections": ["High-Level Structural Overview", "Modular Component Interaction", "Data Security and Flow Design", "Asynchronous Messaging Patterns", "Fault Tolerance Design"] },
                    { "title": "5. Implementation Logic and Process Flow", "key": "implementation", "subsections": ["Core Development Frameworks", "API Integration Strategy", "Business Logic Orchestration", "Security & Identity Management", "Quality Assurance Protocols"] },
                    { "title": "6. Empirical Performance and Results", "key": "results_analysis", "subsections": ["Benchmarking and Technical KPIs", "Critical Analysis of Outcomes", "Efficiency & Latency Evaluation", "Scalability Stress Testing", "Optimization Reports"] },
                    { "title": "7. Strategic Future Scope and Evolution", "key": "future_scope", "subsections": ["Emerging Tech Integration Pipeline", "Long-term Scalability Roadmap", "Market Competitiveness Strategy", "Post-Deployment Lifecycle", "Innovation Vectors"] },
                    { "title": "8. Conclusion and Strategic Synthesis", "key": "conclusion", "subsections": ["Final Technical Synthesis", "Strategic Final Recommendations", "Critical Project Evaluation", "Closing Executive Remarks"] }
                ]
            }

        # Phase 2: Parallel Generation
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [PHASE 2] Starting Parallel Generation (Turbo)...", flush=True)
            
            final_content = {
                "title": request.title,
                "project_type": request.project_type,
                "abstract": outline.get("abstract_plan", "Introduction to " + request.title),
                "objectives": [],
                "tools_technologies": [],
                "image_prompts": []
            }
            
            sections = outline.get("sections", [])
            total_sections = len(sections)
            words_per = (request.pages * 400) // max(total_sections, 1)
            
            tasks = [
                self._generate_section(i, total_sections, request, sec, words_per)
                for i, sec in enumerate(sections)
            ]
            
            results = await asyncio.gather(*tasks)
            
            for sec_key, chapter_data in results:
                final_content[sec_key] = chapter_data
            
            # Apply key healing to align AI output with PDF schema
            final_content = self._heal_keys(final_content)
                
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [FINISH] All chapters combined successfully!", flush=True)
            return final_content
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [CRITICAL] Generation flow crashed: {e}", flush=True)
            raise e

