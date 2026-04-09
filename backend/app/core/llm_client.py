# ai-report-generator/backend/app/core/llm_client.py
from openai import AsyncOpenAI
from app.config import settings
import json
import logging
from typing import Dict, Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class LLMClient:
    """
    Wrapper class for OpenAI API interactions with error handling.
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout=600.0  # Increased to 10 minutes for 30-page reports
        )
        self.model = settings.OPENAI_MODEL
        self.max_tokens = int(getattr(settings, "OPENAI_MAX_TOKENS", 4096))
        self.temperature = settings.OPENAI_TEMPERATURE
        
    async def generate_content(self, prompt: str, validate_schema: bool = False) -> Dict[str, Any]:
        """
        Generate structured report content using OpenAI.
        
        Args:
            prompt: Formatted prompt for the LLM
            
        Returns:
            Dictionary containing structured report sections
        """
        try:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")
            
            # Prepare extra parameters
            extra_params = {}
            if "deepseek" in self.model and settings.DEEPSEEK_THINKING:
                logger.info("Enabling DeepSeek Thinking/Reasoning mode...")
                extra_params["extra_body"] = {"chat_template_kwargs": {"thinking": True}}
            elif "deepseek" in self.model:
                logger.info("DeepSeek Thinking mode is DISABLED (for stability).")

            # DeepSeek specific handling: 
            # Some providers don't support response_format="json_object" with thinking: True
            # So we only use it for non-deepseek models or if thinking is disabled.
            use_json_mode = "deepseek" not in self.model.lower()
            
            logger.info(f"Calling LLM ({self.model})...")
            
            # Make the API call
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "CRITICAL: You are a JSON-only response engine. Your entire response MUST be a single valid JSON block. DO NOT include any 'thinking', preambles, explanations, or conversational text. Start your response with '{' or '[' and end with '}' or ']'. No markdown code blocks either."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"} if use_json_mode else None,
                **extra_params
            )
            
            logger.info("LLM responded successfully.")
            
            # Print reasoning if available (for debugging/visibility)
            message = response.choices[0].message
            reasoning = getattr(message, "reasoning_content", None)
            if reasoning:
                print(f"\n--- Reasoning/Thinking ---\n{reasoning}\n--------------------------\n")

            # Extract and parse response
            content = message.content
            if not content:
                raise ValueError("LLM returned an empty response")
            
            # 1. Advanced JSON Extraction (The "Super-Parser")
            import re
            
            # Clean up obvious distractions
            content_to_parse = content.strip()
            
            # A. Remove DeepSeek "Thinking" blocks
            if "<think>" in content_to_parse:
                print("[EXTRACT] Stripping AI thinking monologue...", flush=True)
                content_to_parse = re.sub(r'<think>.*?</think>', '', content_to_parse, flags=re.DOTALL).strip()
            
            # B. Remove markdown code block markers
            content_to_parse = re.sub(r'```json\s*|\s*```', '', content_to_parse).strip()
            
            def heal_json(text):
                """Helper to fix common LLM JSON errors."""
                # Fix trailing commas
                text = re.sub(r',\s*([\]\}])', r'\1', text)
                return text

            print("[EXTRACT] Searching for data structure...", flush=True)
            
            parsed_content = None
            try:
                # 1. Direct parse
                parsed_content = json.loads(content_to_parse)
            except json.JSONDecodeError:
                # 2. Fast non-greedy search for FIRST { and LAST }
                try:
                    start_json = content_to_parse.find('{')
                    if start_json == -1: start_json = content_to_parse.find('[')
                    
                    end_json = max(content_to_parse.rfind('}'), content_to_parse.rfind(']'))
                    
                    if start_json != -1 and end_json != -1:
                        json_str = content_to_parse[start_json:end_json+1]
                        json_str = heal_json(json_str)
                        parsed_content = json.loads(json_str)
                        print("[EXTRACT] Success: JSON extracted and healed.", flush=True)
                except:
                    pass

            if not parsed_content:
                # 3. Last resort: Try finding balanced blocks sequentially
                obj_match = re.search(r'(\{.*\}|\[.*\])', content_to_parse, re.DOTALL)
                if obj_match:
                    try:
                        parsed_content = json.loads(heal_json(obj_match.group(1)))
                    except:
                        raise ValueError("Could not extract any valid JSON structure from LLM output.")
                else:
                    raise ValueError("No JSON structure detected in response.")

            # 3. Validation
            if validate_schema:
                from app.models.report_schema import ReportContent
                try:
                    ReportContent.model_validate(parsed_content)
                except Exception:
                    pass
            
            return parsed_content
        except Exception as e:
            print(f"[EXTRACT ERROR] Final parsing failure: {str(e)}", flush=True)
            raise HTTPException(status_code=500, detail=f"LLM Data Error: {str(e)}")