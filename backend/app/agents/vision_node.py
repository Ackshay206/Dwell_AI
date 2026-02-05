"""
Vision Node

Handles room image analysis using Gemini Vision.
Migrated from core/vision_service.py.
"""

import json
import base64
import io
from typing import List, Optional
from PIL import Image
from google import genai
from google.genai import types

from app.config import get_settings
from app.models.room import RoomObject, RoomDimensions, ObjectType, VisionOutput


# Prompt for room analysis
ROOM_ANALYSIS_PROMPT = """Analyze this floor plan or room image from a top-down view and detect all furniture and structural elements.

IMPORTANT: First identify the interior room boundaries (the walls). Provide the bounding box of the main room interior space as wall_bounds.

For each object, provide:
1. A unique id (e.g., "bed_1", "desk_1", "door_1")
2. The object label (bed, desk, chair, sofa, door, window, wardrobe, nightstand, refrigerator, toilet, sink, etc.)
3. The bounding box as box_2d: [ymin, xmin, ymax, xmax] normalized to 0-1000
4. The type: "movable" for furniture, "structural" for doors/windows/walls

Also estimate the room dimensions based on typical furniture sizes.

Return ONLY valid JSON in this exact format:
{
    "room_dimensions": {
        "width_estimate": <number>,
        "height_estimate": <number>
    },
    "wall_bounds": [ymin, xmin, ymax, xmax],
    "objects": [
        {
            "id": "<unique_id>",
            "label": "<object_type>",
            "box_2d": [ymin, xmin, ymax, xmax],
            "type": "movable" | "structural"
        }
    ]
}
"""


class VisionAgent:
    """
    Agent for analyzing room images and extracting object data.
    """
    
    def __init__(self):
        settings = get_settings()
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model = settings.model_name

    async def analyze_room(self, image_base64: str) -> VisionOutput:
        """
        Analyze a room image using Gemini Vision.
        
        Args:
            image_base64: Room photo as base64 string
            
        Returns:
            VisionOutput with detected objects and room dimensions
        """
        # Decode image to get dimensions
        image = self._decode_base64_image(image_base64)
        image_width, image_height = image.size
        
        # Configure for JSON output
        config = types.GenerateContentConfig(
            response_mime_type="application/json"
        )
        
        # Call Gemini
        response = self.client.models.generate_content(
            model=self.model,
            contents=[image, ROOM_ANALYSIS_PROMPT],
            config=config
        )
        
        # Parse response
        return self._parse_gemini_response(
            response.text,
            image_width,
            image_height
        )

    def _decode_base64_image(self, image_base64: str) -> Image.Image:
        """Decode base64 string to PIL Image."""
        # Remove data URL prefix if present
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        
        image_data = base64.b64decode(image_base64)
        return Image.open(io.BytesIO(image_data))

    def _convert_box_2d_to_bbox(
        self,
        box_2d: List[int], 
        image_width: int, 
        image_height: int
    ) -> List[int]:
        """Convert normalized [ymin, xmin, ymax, xmax] to [x, y, width, height]."""
        ymin, xmin, ymax, xmax = box_2d
        
        # Convert from 0-1000 to actual pixels
        x = int(xmin / 1000 * image_width)
        y = int(ymin / 1000 * image_height)
        width = int((xmax - xmin) / 1000 * image_width)
        height = int((ymax - ymin) / 1000 * image_height)
        
        return [x, y, width, height]

    def _parse_gemini_response(
        self,
        response_text: str,
        image_width: int,
        image_height: int
    ) -> VisionOutput:
        """Parse Gemini's JSON response into VisionOutput schema."""
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Gemini response as JSON: {e}")
        
        # Parse room dimensions
        dims = data.get("room_dimensions", {})
        room_dimensions = RoomDimensions(
            width_estimate=dims.get("width_estimate", image_width),
            height_estimate=dims.get("height_estimate", image_height)
        )
        
        # Parse wall bounds
        wall_bounds = None
        if "wall_bounds" in data and data["wall_bounds"]:
            wall_bounds = self._convert_box_2d_to_bbox(data["wall_bounds"], image_width, image_height)
        
        # Parse objects
        objects = []
        for obj_data in data.get("objects", []):
            obj_type = ObjectType.STRUCTURAL if obj_data.get("type") == "structural" else ObjectType.MOVABLE
            
            # Convert bounding box format
            box_2d = obj_data.get("box_2d", [0, 0, 100, 100])
            bbox = self._convert_box_2d_to_bbox(box_2d, image_width, image_height)
            
            room_obj = RoomObject(
                id=obj_data.get("id", f"obj_{len(objects)}"),
                label=obj_data.get("label", "unknown"),
                bbox=bbox,
                type=obj_type,
                orientation=0
            )
            objects.append(room_obj)
        
        return VisionOutput(
            room_dimensions=room_dimensions,
            objects=objects,
            wall_bounds=wall_bounds
        )
