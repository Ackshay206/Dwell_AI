"""
Perspective Generator

Converts top-down layout JSON → Photorealistic 2D side-view image.

Uses Gemini 2.5 Flash Image model for image generation to create
realistic eye-level perspective views of the optimized room layout.
"""

import os
import json
import base64
import asyncio
from typing import List, Optional, Dict, Any
from google import genai
from google.genai import types

from app.models.state import AgentState
from app.models.room import RoomObject, RoomDimensions


class PerspectiveGenerator:
    """
    Generates photorealistic 2D side-view renders from top-down layout data.
    
    Uses RenderImageTool for image generation with detailed
    prompts that describe the room layout, materials, and style.
    """
    
    def __init__(self):
        from app.tools.generate_image import RenderImageTool
        self.tool = RenderImageTool()
        from app.config import get_settings
        self.image_model = get_settings().image_model_name
    
    async def generate_side_view(
        self, 
        layout: List[RoomObject],
        room_dims: RoomDimensions,
        style: str = "modern",
        view_angle: str = "corner",
        lighting: str = "natural daylight"
    ) -> str:
        """
        Generate a photorealistic eye-level view of the room.
        
        Args:
            layout: List of room objects with positions
            room_dims: Room dimensions
            style: Design style (modern, minimalist, cozy, scandinavian, industrial)
            view_angle: Viewing angle (corner, front wall, bed view, desk view)
            lighting: Lighting conditions (natural daylight, evening warm, night ambient)
            
        Returns:
            Base64 encoded image string of the rendered perspective
        """
        # Build detailed scene description from layout
        scene_description = self._build_scene_description(layout, room_dims, style)
        
        prompt = f"""Generate a photorealistic interior design render of a bedroom.

STYLE: {style}
VIEWING ANGLE: {view_angle} perspective, eye-level (standing human height ~5.5ft)
LIGHTING: {lighting}

ROOM LAYOUT DESCRIPTION:
{scene_description}

RENDERING REQUIREMENTS:
1. Photorealistic quality with detailed textures and materials
2. Accurate proportions based on the layout description
3. Natural shadows and reflections
4. {style} interior design aesthetic
5. High-resolution, magazine-quality render
6. Warm, inviting atmosphere

Generate a single beautiful interior photograph-style image showing this room from the {view_angle} angle.
The image should look like a professional real estate or interior design photograph."""

        try:
            # delegated to tool
            return self.tool.generate_image(prompt)
            
        except Exception as e:
            raise RuntimeError(f"Perspective generation failed: {e}")
    
    def _build_scene_description(
        self, 
        layout: List[RoomObject], 
        room_dims: RoomDimensions,
        style: str
    ) -> str:
        """
        Convert layout JSON into natural language scene description.
        
        Args:
            layout: List of room objects
            room_dims: Room dimensions
            style: Design style
            
        Returns:
            Detailed natural language description of the room
        """
        # Group objects by z_index for layered description
        floor_items = []
        furniture = []
        structural = []
        
        for obj in layout:
            item_desc = self._describe_object(obj, room_dims)
            
            if obj.label in ['door', 'window', 'wall']:
                structural.append(item_desc)
            elif obj.z_index == 0:
                floor_items.append(item_desc)
            else:
                furniture.append(item_desc)
        
        # Build comprehensive description
        description = f"""Room Size: Approximately {room_dims.width_estimate} x {room_dims.height_estimate} feet

STRUCTURAL ELEMENTS:
{chr(10).join(structural) if structural else "- Standard walls with one entrance"}

FLOOR ELEMENTS:
{chr(10).join(floor_items) if floor_items else "- Clean hardwood or carpet flooring"}

FURNITURE ARRANGEMENT:
{chr(10).join(furniture) if furniture else "- Empty room"}

STYLE DETAILS for {style}:
"""
        
        # Add style-specific details
        style_details = {
            "modern": "- Clean lines, neutral colors with bold accents\n- Minimal clutter, sleek furniture\n- Chrome or matte black hardware",
            "minimalist": "- White and light grey color palette\n- Essential furniture only\n- Hidden storage, clean surfaces",
            "cozy": "- Warm earth tones, soft textures\n- Plush bedding, throw pillows\n- Warm lighting, plants",
            "scandinavian": "- Light wood tones, white walls\n- Functional, simple furniture\n- Natural materials, hygge atmosphere",
            "industrial": "- Exposed brick or concrete accents\n- Metal and wood combinations\n- Edison bulbs, raw materials"
        }
        
        description += style_details.get(style, style_details["modern"])
        
        return description
    
    def _describe_object(self, obj: RoomObject, room_dims: RoomDimensions) -> str:
        """
        Convert a single object to natural language description.
        
        Args:
            obj: Room object to describe
            room_dims: Room dimensions for relative positioning
            
        Returns:
            Natural language description of the object
        """
        # Calculate position description
        x_pct = obj.bbox[0]
        y_pct = obj.bbox[1]
        
        # Determine position in room
        x_pos = "left" if x_pct < 33 else ("center" if x_pct < 66 else "right")
        y_pos = "front" if y_pct < 33 else ("middle" if y_pct < 66 else "back")
        
        # Orientation description
        orientation_map = {0: "facing north (away from viewer)", 
                          90: "facing east (to the right)",
                          180: "facing south (toward viewer)", 
                          270: "facing west (to the left)"}
        orientation_desc = orientation_map.get(obj.orientation, "")
        
        # Material description
        material = f" made of {obj.material_hint}" if obj.material_hint else ""
        
        # Build description
        desc = f"- {obj.label.title()}{material} positioned in the {y_pos}-{x_pos} area of the room"
        
        if obj.label in ['bed', 'desk', 'sofa', 'chair'] and orientation_desc:
            desc += f", {orientation_desc}"
        
        return desc
    
    async def generate_thumbnail(
        self, 
        layout: List[RoomObject],
        room_dims: RoomDimensions,
        style: str = "modern"
    ) -> str:
        """
        Generate a quick thumbnail preview of the layout.
        
        Uses a simpler prompt for faster generation.
        
        Returns:
            Base64 encoded thumbnail image
        """
        # Simplified prompt for faster thumbnail generation
        furniture_list = ", ".join([obj.label for obj in layout if obj.type.value == "movable"])
        
        prompt = f"""Quick sketch-style overhead view of a bedroom with: {furniture_list}.
{style} style, simple clean illustration, top-down perspective.
Show furniture placement clearly, minimal details, clean lines."""

        try:
            response = self.client.models.generate_content(
                model=self.image_model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["image", "text"]
                )
            )
            
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    image_data = part.inline_data.data
                    return base64.b64encode(image_data).decode('utf-8')
            
            return ""  # Return empty if no image
            
        except Exception:
            return ""  # Silently fail for thumbnails


async def perspective_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node that generates perspective renders.
    
    Takes the selected layout and generates a photorealistic side-view image.
    
    Args:
        state: Current agent state with proposed_layout
        
    Returns:
        State updates with rendered image
    """
    generator = PerspectiveGenerator()
    
    try:
        layout = state.get("proposed_layout") or state.get("current_layout", [])
        room_dims = state["room_dimensions"]
        
        # Generate the main perspective view
        image_base64 = await generator.generate_side_view(
            layout=layout,
            room_dims=room_dims,
            style="modern",  # Could be made configurable
            view_angle="corner",
            lighting="natural daylight"
        )
        
        return {
            "output_image_url": None,  # Not using URL, using base64
            "output_image_base64": image_base64,
            "explanation": state.get("explanation", "") + "\n\nGenerated photorealistic perspective view.",
        }
        
    except Exception as e:
        return {
            "error": f"Perspective generation failed: {str(e)}",
            "output_image_base64": None
        }


def perspective_node_sync(state: AgentState) -> Dict[str, Any]:
    """
    Synchronous wrapper for the perspective node (for LangGraph compatibility).
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, safe to use asyncio.run()
        return asyncio.run(perspective_node(state))
    else:
        # Already in an async context, run in new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, perspective_node(state))
            return future.result()
