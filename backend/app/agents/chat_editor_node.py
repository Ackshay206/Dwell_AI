"""
Chat Editor Node

Conversational image editing agent that allows natural language
commands to modify the rendered room perspective.

Supports surgical editing commands like:
- "Move the desk to the left"
- "Change the bed to face the window"
- "Add a plant in the corner"
- "Make the room feel more cozy"
"""

import os
import json
import base64
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from google import genai
from google.genai import types

from app.models.state import AgentState
from app.models.room import RoomObject, RoomDimensions


class ChatEditor:
    """
    Conversational editing agent for room layouts and renders.
    
    Parses natural language editing commands and applies changes
    either to the layout data (for structural edits) or to the
    rendered image (for cosmetic edits).
    """
    
    def __init__(self):
        from app.config import get_settings
        from app.tools.edit_image import EditImageTool
        
        settings = get_settings()
        api_key = settings.google_api_key
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in .env file")
        self.client = genai.Client(api_key=api_key)
        self.reasoning_model = settings.model_name  # For understanding commands
        self.image_model = settings.image_model_name  # For image edits
        self.edit_tool = EditImageTool()
    
    async def process_edit_command(
        self,
        command: str,
        current_layout: List[RoomObject],
        room_dims: RoomDimensions,
        current_image_base64: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a natural language editing command.
        
        Args:
            command: Natural language edit command from user
            current_layout: Current room layout
            room_dims: Room dimensions
            current_image_base64: Current rendered image (if available)
            
        Returns:
            Dictionary with:
                - edit_type: "layout" or "cosmetic"
                - updated_layout: New layout if layout edit
                - updated_image_base64: New image if cosmetic edit
                - explanation: What was changed
        """
        # First, classify the edit type
        edit_type, parsed_command = await self._parse_command(command, current_layout)
        
        if edit_type == "layout":
            # Structural edit - modify layout positions
            updated_layout, explanation = await self._apply_layout_edit(
                parsed_command, current_layout, room_dims
            )
            return {
                "edit_type": "layout",
                "updated_layout": updated_layout,
                "updated_image_base64": None,  # Will need re-render
                "explanation": explanation,
                "needs_rerender": True
            }
        else:
            # Cosmetic edit - modify the image directly
            if current_image_base64:
                updated_image, explanation = await self._apply_image_edit(
                    parsed_command, current_image_base64
                )
                return {
                    "edit_type": "cosmetic",
                    "updated_layout": current_layout,  # Unchanged
                    "updated_image_base64": updated_image,
                    "explanation": explanation,
                    "needs_rerender": False
                }
            else:
                return {
                    "edit_type": "error",
                    "updated_layout": current_layout,
                    "updated_image_base64": None,
                    "explanation": "No rendered image available for cosmetic editing. Please generate a render first.",
                    "needs_rerender": True
                }
    
    async def _parse_command(
        self, 
        command: str, 
        current_layout: List[RoomObject]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Parse natural language command into structured edit instruction.
        
        Returns:
            Tuple of (edit_type, parsed_command_dict)
        """
        furniture_list = [{"id": obj.id, "label": obj.label} for obj in current_layout]
        
        prompt = f"""You are an interior design assistant parsing user edit commands.

CURRENT FURNITURE IN ROOM:
{json.dumps(furniture_list, indent=2)}

USER COMMAND: "{command}"

Classify this command and parse it into a structured format.

EDIT TYPES:
1. "layout" - Commands that move, rotate, or reposition furniture
   Examples: "move desk to left", "rotate bed 90 degrees", "swap desk and dresser"
   
2. "cosmetic" - Commands that change style, color, lighting, or add decorations
   Examples: "make it more cozy", "add plants", "change lighting to evening", "paint walls blue"

Return JSON with this schema:
{{
  "edit_type": "layout" or "cosmetic",
  "action": "move|rotate|swap|add|remove|change_style|change_color|change_lighting",
  "target_object": "object_id or null",
  "target_label": "object label if no ID matched",
  "parameters": {{
    "direction": "left|right|up|down|null",
    "distance": "small|medium|large|null",
    "rotation": 0-360 or null,
    "swap_with": "object_id or null",
    "style": "description or null",
    "color": "color or null"
  }},
  "natural_description": "What the user wants in plain English"
}}
"""
        
        try:
            response = self.client.models.generate_content(
                model=self.reasoning_model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            parsed = json.loads(response.text)
            return parsed.get("edit_type", "layout"), parsed
            
        except Exception:
            # Default to layout edit if parsing fails
            return "layout", {
                "action": "unknown",
                "natural_description": command
            }
    
    async def _apply_layout_edit(
        self,
        parsed_command: Dict[str, Any],
        current_layout: List[RoomObject],
        room_dims: RoomDimensions
    ) -> Tuple[List[RoomObject], str]:
        """
        Apply a layout modification based on parsed command.
        
        Returns:
            Tuple of (updated_layout, explanation)
        """
        action = parsed_command.get("action", "")
        target_id = parsed_command.get("target_object")
        target_label = parsed_command.get("target_label")
        params = parsed_command.get("parameters", {})
        
        # Find target object
        target_obj = None
        for obj in current_layout:
            if target_id and obj.id == target_id:
                target_obj = obj
                break
            elif target_label and obj.label.lower() == target_label.lower():
                target_obj = obj
                break
        
        if not target_obj and action in ["move", "rotate"]:
            return current_layout, f"Could not find the object to edit. Available objects: {[o.label for o in current_layout]}"
        
        # Create updated layout
        updated_layout = []
        explanation = ""
        
        for obj in current_layout:
            new_obj = RoomObject(
                id=obj.id,
                label=obj.label,
                bbox=obj.bbox.copy(),
                type=obj.type,
                orientation=obj.orientation,
                is_locked=obj.is_locked,
                z_index=obj.z_index,
                material_hint=obj.material_hint
            )
            
            if target_obj and obj.id == target_obj.id:
                if action == "move":
                    direction = params.get("direction", "")
                    distance_map = {"small": 5, "medium": 10, "large": 20}
                    distance = distance_map.get(params.get("distance", "medium"), 10)
                    
                    if direction == "left":
                        new_obj.bbox[0] = max(0, new_obj.bbox[0] - distance)
                    elif direction == "right":
                        new_obj.bbox[0] = min(100 - new_obj.bbox[2], new_obj.bbox[0] + distance)
                    elif direction == "up":
                        new_obj.bbox[1] = max(0, new_obj.bbox[1] - distance)
                    elif direction == "down":
                        new_obj.bbox[1] = min(100 - new_obj.bbox[3], new_obj.bbox[1] + distance)
                    
                    explanation = f"Moved {obj.label} {direction} by {distance}%"
                
                elif action == "rotate":
                    rotation = params.get("rotation", 90)
                    new_obj.orientation = (new_obj.orientation + rotation) % 360
                    explanation = f"Rotated {obj.label} by {rotation} degrees (now facing {new_obj.orientation}°)"
            
            updated_layout.append(new_obj)
        
        if not explanation:
            explanation = f"Processed command: {parsed_command.get('natural_description', 'Unknown edit')}"
        
        return updated_layout, explanation
    
    async def _apply_image_edit(
        self,
        parsed_command: Dict[str, Any],
        current_image_base64: str
    ) -> Tuple[str, str]:
        """
        Apply a cosmetic edit to the rendered image using EditImageTool.
        
        Returns:
            Tuple of (new_image_base64, explanation)
        """
        edit_description = parsed_command.get("natural_description", "Apply the requested change")
        
        try:
            # Delegate to EditImageTool
            new_image = await self.edit_tool.edit_image(
                base_image=current_image_base64,
                instruction=edit_description
            )
            return new_image, f"Applied: {edit_description}"
            
        except Exception as e:
            return current_image_base64, f"Edit failed: {str(e)}"


async def chat_editor_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node for conversational editing.
    
    Processes edit commands from the user and updates layout or image.
    
    Args:
        state: Current agent state with edit_command
        
    Returns:
        State updates with edited layout/image
    """
    editor = ChatEditor()
    
    edit_command = state.get("edit_command", "")
    if not edit_command:
        return {
            "explanation": "No edit command provided. Use natural language to describe changes like 'move the desk to the left' or 'make the room more cozy'."
        }
    
    try:
        result = await editor.process_edit_command(
            command=edit_command,
            current_layout=state.get("current_layout", []),
            room_dims=state["room_dimensions"],
            current_image_base64=state.get("output_image_base64")
        )
        
        updates = {
            "explanation": result["explanation"],
            "should_continue": result.get("needs_rerender", False)
        }
        
        if result["edit_type"] == "layout" and result["updated_layout"]:
            updates["current_layout"] = result["updated_layout"]
            updates["proposed_layout"] = result["updated_layout"]
        
        if result["updated_image_base64"]:
            updates["output_image_base64"] = result["updated_image_base64"]
        
        return updates
        
    except Exception as e:
        return {
            "error": f"Chat editor failed: {str(e)}",
            "explanation": f"Could not process edit command: {str(e)}"
        }


def chat_editor_node_sync(state: AgentState) -> Dict[str, Any]:
    """
    Synchronous wrapper for the chat editor node.
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, safe to use asyncio.run()
        return asyncio.run(chat_editor_node(state))
    else:
        # Already in an async context, run in new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, chat_editor_node(state))
            return future.result()
