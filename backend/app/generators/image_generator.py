# # ai-report-generator/backend/app/generators/image_generator.py
# import httpx
# import os
# import urllib.parse
# import logging
# import random
# from typing import List, Dict, Any, Optional
# from app.config import settings
# from app.utils.file_utils import FileUtils

# logger = logging.getLogger(__name__)


# class ImageGenerator:
#     """
#     Fetches topic-relevant real-world photos using LoremFlickr (free, no API key required).
#     Since free AI image APIs like Pollinations now require auth, this provides a reliable alternative.
#     """

#     def __init__(self):
#         self.output_dir = settings.CHARTS_DIR
#         FileUtils.ensure_directory(self.output_dir)

#     async def generate_images(
#         self, report_id: str, image_prompts: List[Dict[str, Any]]
#     ) -> List[Dict[str, str]]:
#         """
#         Fetch relevant images based on LLM-provided prompts using LoremFlickr.

#         Args:
#             report_id: Unique identifier for the report
#             image_prompts: List of dicts with 'title' and 'prompt' keys

#         Returns:
#             List of dicts with 'path' and 'title' for each generated image
#         """
#         results = []

#         if not image_prompts:
#             logger.warning("No image prompts provided, skipping image generation")
#             return results

#         # Limit to 3 images max to keep report reasonable
#         prompts_to_use = image_prompts[:3]

#         for i, img_data in enumerate(prompts_to_use):
#             title = img_data.get("title", f"Figure {i + 1}")
#             prompt = img_data.get("prompt", title) # Use prompt or fallback to title

#             if not prompt:
#                 continue
            
#             # Extract main keywords from the prompt to use for image search
#             keywords = self._extract_keywords(prompt, title)
            
#             image_path = await self._download_image(report_id, i, keywords)
#             if image_path:
#                 results.append({"path": image_path, "title": title})

#         logger.info(f"Generated {len(results)} images for report {report_id}")
#         return results

#     def _extract_keywords(self, prompt: str, title: str) -> str:
#         """Extract main conceptual keywords from a long prompt description."""
#         # Simple extraction: just combine title and prompt, take some interesting words
#         combined = f"{title} {prompt}".lower()
        
#         # Determine the theme based on common report topics
#         theme = "business"
#         if any(word in combined for word in ["ai", "machine learning", "neural", "robot", "algorithm"]):
#             theme = "artificial_intelligence"
#         elif any(word in combined for word in ["cloud", "server", "architecture", "database", "api"]):
#             theme = "technology"
#         elif any(word in combined for word in ["eco", "renewable", "solar", "wind", "nature", "environment"]):
#             theme = "renewable_energy"
#         elif any(word in combined for word in ["health", "medical", "doctor", "patient"]):
#             theme = "medicine"
            
#         return theme

#     async def _download_image(
#         self, report_id: str, index: int, keywords: str
#     ) -> Optional[str]:
#         """
#         Download a high-quality relevant photo from LoremFlickr.
#         """
#         try:
#             # LoremFlickr provides random Creative Commons photos matching keywords
#             # For example: https://loremflickr.com/1024/768/technology?lock=123
#             # We use a random lock ID to ensure we get a specific image, but different ones per section
#             lock_id = random.randint(1, 10000)
#             url = f"https://loremflickr.com/1024/768/{keywords}?lock={lock_id}"

#             filename = f"image_{report_id}_{index}.png"
#             filepath = os.path.join(self.output_dir, filename)

#             async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
#                 response = await client.get(url)
#                 response.raise_for_status()

#                 # Verify we got an image
#                 content_type = response.headers.get("content-type", "")
#                 if "image" not in content_type:
#                     logger.error(
#                         f"Image provider returned non-image content: {content_type}"
#                     )
#                     return None

#                 # Save to file
#                 with open(filepath, "wb") as f:
#                     f.write(response.content)

#             logger.info(f"Image downloaded: {filepath}")
#             return filepath

#         except httpx.TimeoutException:
#             logger.error(f"Timeout downloading image for keywords: {keywords}")
#             return None
#         except Exception as e:
#             logger.error(f"Image download failed for keywords '{keywords}': {e}")
#             return None


# ai-report-generator/backend/app/generators/image_generator.py

import httpx
import os
import logging
import urllib.parse
from typing import List, Dict, Any, Optional
from app.config import settings
from app.utils.file_utils import FileUtils

logger = logging.getLogger(__name__)


class ImageGenerator:
    """
    Hybrid Image Generator:
    1. Try AI images (Pollinations)
    2. Fallback to LoremFlickr (reliable)
    """

    def __init__(self):
        self.output_dir = settings.CHARTS_DIR
        FileUtils.ensure_directory(self.output_dir)

    async def generate_images(
        self, report_id: str, image_prompts: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        results = []

        if not image_prompts:
            logger.warning("No image prompts provided")
            return results

        prompts_to_use = image_prompts[:3]

        for i, img_data in enumerate(prompts_to_use):
            title = img_data.get("title", f"Figure {i+1}")
            prompt = img_data.get("prompt", title)

            if not prompt:
                continue

            enhanced_prompt = f"{prompt}, high quality, realistic"

            # 🔥 Try AI first
            image_path = await self._generate_ai_image(report_id, i, enhanced_prompt)

            # 🔁 Fallback if AI fails
            if not image_path:
                logger.warning("🔁 Falling back to LoremFlickr...")
                keywords = self._extract_keywords(prompt)
                image_path = await self._fallback_image(report_id, i, keywords)

            if image_path:
                results.append({"path": image_path, "title": title})

        logger.info(f"Generated {len(results)} images")
        return results

    def _extract_keywords(self, prompt: str) -> str:
        words = prompt.lower().split()
        stop_words = {"the", "and", "of", "in", "on", "with", "a", "an", "to"}
        words = [w for w in words if w not in stop_words]
        return ",".join(words[:3]) if words else "technology"

    async def _generate_ai_image(
        self, report_id: str, index: int, prompt: str
    ) -> Optional[str]:
        try:
            encoded_prompt = urllib.parse.quote(prompt)

            url = f"https://gen.pollinations.ai/image/{encoded_prompt}?width=1024&height=768"

            filename = f"image_{report_id}_{index}.jpg"
            filepath = os.path.join(self.output_dir, filename)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)

                if response.status_code != 200:
                    return None

                if "image" not in response.headers.get("content-type", ""):
                    return None

                with open(filepath, "wb") as f:
                    f.write(response.content)

            logger.info(f"✅ AI Image: {filepath}")
            return filepath

        except Exception:
            return None

    async def _fallback_image(
        self, report_id: str, index: int, keywords: str
    ) -> Optional[str]:
        try:
            url = f"https://loremflickr.com/1024/768/{keywords}"

            filename = f"image_{report_id}_{index}.jpg"
            filepath = os.path.join(self.output_dir, filename)

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

                if "image" not in response.headers.get("content-type", ""):
                    return None

                with open(filepath, "wb") as f:
                    f.write(response.content)

            logger.info(f"✅ Fallback Image: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"❌ Fallback failed: {e}")
            return None