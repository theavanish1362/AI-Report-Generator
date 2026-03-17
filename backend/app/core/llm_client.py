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
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.max_tokens = settings.OPENAI_MAX_TOKENS
        self.temperature = settings.OPENAI_TEMPERATURE
        
    async def generate_content(self, prompt: str) -> Dict[str, Any]:
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
            
            # Make the API call
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional report generator. Always return your response in JSON format according to the requested structure."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            # Extract and parse response
            content = response.choices[0].message.content
            
            # Parse JSON response
            try:
                parsed_content = json.loads(content)
                return parsed_content
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI response as JSON: {e}")
                raise HTTPException(status_code=500, detail="Failed to generate valid report content")
                
        except Exception as e:
            logger.error(f"Error in OpenAI client: {str(e)}")
            raise HTTPException(status_code=500, detail=f"LLM service error: {str(e)}")