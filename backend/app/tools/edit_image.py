"""
Edit Image Tool

Tools for editing existing images based on prompts and masks.
Used by Chat Editor Agent.
"""

import base64
import io
import asyncio
from typing import List, Optional
from google import genai
from google.genai import types
from PIL import Image

from app.config import get_settings


class EditImageTool:
    """
    Tool for applying surgical edits to images.
    """
    
    def __init__(self):
        settings = get_settings()
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model = settings.image_model_name
    
    async def edit_image(
        self, 
        base_image: str, 
        instruction: str, 
        mask_base64: Optional[str] = None
    ) -> str:
        """
        Apply edits to an image based on instruction.
        
        Args:
            base_image: Base64 encoded original image
            instruction: Text instruction for the edit
            mask_base64: Optional base64 mask defining edit region
            
        Returns:
            Base64 encoded edited image
        """
        # Handle data URL prefix
        if "," in base_image:
            base_image = base_image.split(",")[1]
            
        current_image_data = base64.b64decode(base_image)
        
        # If mask is provided, we could use it to refine the prompt or generic mask handling
        # For now, we rely on the prompt instructing the model where to focus
        
        prompt = f"""Edit this interior room image.
INSTRUCTION: {instruction}
Keep everything else exactly the same.
Maintain photorealistic quality and consistent lighting."""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(
                        data=current_image_data, 
                        mime_type="image/jpeg"
                    ),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"]
                )
            )
            
            # Extract image from response
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        return base64.b64encode(part.inline_data.data).decode('utf-8')
                        
            raise RuntimeError("No image generated in response")
            
        except Exception as e:
            raise RuntimeError(f"Image editing failed: {str(e)}")
