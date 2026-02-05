"""
Render Image Tool

Tools for generating images based on prompts using Gemini Image Generation.
Used by Designer Agent and Perspective Generator.
"""

import base64
from typing import Optional
from google import genai
from google.genai import types

from app.config import get_settings


class RenderImageTool:
    """
    Tool for generating images from text prompts.
    """
    
    def __init__(self):
        settings = get_settings()
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model = "gemini-2.5-flash-image"  # Image generation model
    
    def generate_image(self, prompt: str) -> str:
        """
        Generate an image from a text prompt.
        
        Args:
            prompt: Detailed description of the image to generate
            
        Returns:
            Base64 encoded image string
        """
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["image", "text"]
                )
            )
            
            # Extract image from response
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        image_data = part.inline_data.data
                        return base64.b64encode(image_data).decode('utf-8')
            
            raise RuntimeError("No image generated in response")
            
        except Exception as e:
            raise RuntimeError(f"Image generation failed: {str(e)}")
