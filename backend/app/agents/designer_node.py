"""
Designer Node (The "Architect Brain")

LLM-powered interior design agent that generates 2-3 distinct, 
architecturally sound layout variations using semantic reasoning.

Replaces the deterministic solver_node.py with generative design.
Validation still uses Python (ConstraintEngine), but generation is semantic.
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

from app.models.state import AgentState
from app.models.room import RoomObject, RoomDimensions, ObjectType
from app.core.constraints import check_all_hard_constraints
from app.core.scoring import score_layout


class InteriorDesignerAgent:
    """
    LLM-powered interior design agent that generates multiple layout variations.
    
    Uses Gemini Pro for stronger reasoning capabilities to create:
    - Flow Optimized layouts (maximize walking space)
    - Zoned Living layouts (distinct functional zones)
    - Creative/Unconventional layouts (bold, artistic arrangements)
    """
    
    def __init__(self):
        from app.config import get_settings
        from app.tools.generate_image import RenderImageTool
        from app.tools.edit_image import EditImageTool
        
        settings = get_settings()
        api_key = settings.google_api_key
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in .env file")
        self.client = genai.Client(api_key=api_key)
        self.model = settings.model_name  # Use model from settings
        self.render_tool = RenderImageTool()
        self.edit_tool = EditImageTool()
    
    async def generate_layout_variations(
        self, 
        current_layout: List[RoomObject],
        room_dims: RoomDimensions,
        locked_ids: List[str],
        image_base64: Optional[str] = None,
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generate 3 distinct layout options using LLM reasoning.
        """
        
        # Separate movable and structural objects
        movable_objects = []
        structural_objects = []
        
        for obj in current_layout:
            obj_dict = {
                "id": obj.id,
                "label": obj.label,
                "bbox": obj.bbox,
                "orientation": obj.orientation,
                "z_index": obj.z_index,
                "material_hint": obj.material_hint
            }
            
            if obj.id in locked_ids or obj.type == ObjectType.STRUCTURAL:
                structural_objects.append(obj_dict)
            else:
                obj_dict["is_locked"] = obj.id in locked_ids
                movable_objects.append(obj_dict)
        
        prompt = f"""You are a Master Interior Architect.
ROOM DIMENSIONS: {room_dims.width_estimate} x {room_dims.height_estimate} feet (0-100 coordinates).

STRUCTURAL ELEMENTS (FIXED - NEVER MOVE):
{json.dumps(structural_objects, indent=2)}

MOVABLE FURNITURE:
{json.dumps(movable_objects, indent=2)}

TASK: Generate EXACTLY 3 DISTINCT layout variations based on these themes:

1. "Work Focused":
   - Prioritize productivity. Desk near window for light.
   - Dedicated workspace zone.

2. "Cozy":
   - Prioritize comfort. Intimate conversation areas.
   - Warm arrangement (e.g., bed in corner).

3. "Creative/Aesthetic":
   - Artistic, unconventional layout.
   - Asymmetrical balance.

MANDATORY PROXIMITY & ZONING RULES:
1. **Nightstands**: MUST be adjacent to the head of the Bed (within 5% distance).
2. **Chairs**: MUST be grouped with Tables or Desks.
3. **Kitchen Zone**: Stovetop and Kitchen Sink MUST be in the same zone (keep them close).
4. **Bathroom Zone**: Toilet, Shower, and Bathroom Sink MUST be in the same zone.
5. **Bed**: Headboard should practically touch a wall.
6. **Context**: Group generic "Sink" objects with their respective zone (Stove=Kitchen, Toilet=Bathroom).

CRITICAL RULES:
1. DO NOT MOVE STRUCTURAL OBJECTS (Doors, Windows).
2. No overlaps. Minimum 5% clearance.
3. Keep objects within bounds (0-100).

OUTPUT JSON:
{{
  "variations": [
    {{ "name": "Work Focused", "description": "...", "objects": [...] }},
    {{ "name": "Cozy", "description": "...", "objects": [...] }},
    {{ "name": "Creative/Aesthetic", "description": "...", "objects": [...] }}
  ]
}}
"""
        
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[prompt],
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                
                data = json.loads(response.text)
                variations = []
                
                # First pass: Process layouts
                for var in data.get("variations", []):
                    new_layout = self._merge_layout(current_layout, var.get("objects", []), locked_ids)
                    
                    # Violations check & fix
                    violations = check_all_hard_constraints(new_layout, int(room_dims.width_estimate), int(room_dims.height_estimate))
                    if violations and len(violations) <= 3:
                         fixed = await self._fix_violations(new_layout, violations, room_dims)
                         if fixed: new_layout = fixed
                    
                    score = score_layout(new_layout, int(room_dims.width_estimate), int(room_dims.height_estimate))
                    
                    variations.append({
                        "name": var.get("name"),
                        "description": var.get("description"),
                        "layout": new_layout,
                        "score": score.total_score,
                        "violations": violations
                    })

                # Second pass: Generate Thumbnails Concurrently
                if image_base64:
                    tasks = []
                    for var in variations:
                        tasks.append(self._generate_layout_thumbnail(
                            image_base64, current_layout, var["layout"]
                        ))
                    
                    thumbnails = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, thumb in enumerate(thumbnails):
                        if isinstance(thumb, str) and thumb:
                            variations[i]["thumbnail_base64"] = thumb
                
                return variations[:3]
                
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"Designer failed: {e}")
        
        raise RuntimeError("Designer agent failed")

    async def _generate_layout_thumbnail(
        self,
        original_image_base64: str,
        current_layout: List[RoomObject],
        new_layout: List[RoomObject]
    ) -> Optional[str]:
        """Generate a photorealistic thumbnail by editing the original image."""
        changes = []
        original_map = {obj.id: obj.bbox for obj in current_layout}
        
        for obj in new_layout:
            if obj.type == ObjectType.STRUCTURAL: continue
            
            orig_bbox = original_map.get(obj.id)
            if orig_bbox and orig_bbox != obj.bbox:
                # Calculate movement vector to give better instructions
                dx = obj.bbox[0] - orig_bbox[0]
                dy = obj.bbox[1] - orig_bbox[1]
                
                # Check significance (threshold 2%)
                if abs(dx) < 2 and abs(dy) < 2:
                    continue
                    
                direction = []
                if abs(dx) > 2:
                    direction.append("right" if dx > 0 else "left")
                if abs(dy) > 2:
                    direction.append("down" if dy > 0 else "up") # Y grows downwards usually in images? No, usually up is up. Assuming screen coords 0,0 top-left.
                                                                 # Actually for room layout 0,0 is typically top-left.
                                                                 # So dy>0 is "down".
                
                dir_str = " and ".join(direction)
                changes.append(f"Move the {obj.label} slightly {dir_str}")
                
        if not changes:
            return None 
            
        # More descriptive instruction for generative model
        instruction = (
            "Create a photorealistic top-down view of this room with the following furniture changes: " + 
            ", ".join(changes) + 
            ". Keep all other furniture, flooring, and lighting exactly the same. "
            "Ensure the result looks like a real photograph."
        )
        
        try:
             # Use the Edit tool
             return await self.edit_tool.edit_image(original_image_base64, instruction)
        except Exception as e:
             # If generation fails, we'll fall back to SVG in frontend
             print(f"Thumbnail generation failed: {e}")
             return None
    
    def _merge_layout(
        self, 
        original: List[RoomObject], 
        llm_updates: List[dict],
        locked_ids: List[str]
    ) -> List[RoomObject]:
        """
        Merge LLM's updated positions with original object data.
        
        Args:
            original: Original list of RoomObjects
            llm_updates: List of position updates from LLM
            locked_ids: IDs of locked objects (should not be updated)
            
        Returns:
            New list of RoomObjects with updated positions
        """
        updated_map = {obj["id"]: obj for obj in llm_updates}
        new_layout = []
        
        for obj in original:
            # Create a copy of the object
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
            
            # Update position if we have LLM updates and object is not locked
            if obj.id in updated_map and obj.id not in locked_ids and obj.type != ObjectType.STRUCTURAL:
                llm_obj = updated_map[obj.id]
                if "bbox" in llm_obj:
                    new_obj.bbox = [int(b) for b in llm_obj["bbox"]]
                if "orientation" in llm_obj:
                    new_obj.orientation = int(llm_obj.get("orientation", obj.orientation))
            
            new_layout.append(new_obj)
        
        return new_layout
    
    async def _fix_violations(
        self, 
        layout: List[RoomObject], 
        violations: List, 
        room_dims: RoomDimensions
    ) -> Optional[List[RoomObject]]:
        """
        Ask LLM to fix specific constraint violations (feedback loop).
        
        Args:
            layout: Current layout with violations
            violations: List of constraint violations
            room_dims: Room dimensions
            
        Returns:
            Fixed layout or None if fix failed
        """
        if not violations:
            return layout
            
        violation_desc = "\n".join([f"- {v.description}" for v in violations[:5]])
        
        movable_layout = [
            {"id": o.id, "label": o.label, "bbox": o.bbox, "orientation": o.orientation}
            for o in layout if o.type != ObjectType.STRUCTURAL
        ]
        
        prompt = f"""The layout you generated has these CONSTRAINT VIOLATIONS:
{violation_desc}

Current layout of MOVABLE objects:
{json.dumps(movable_layout, indent=2)}

Room dimensions: {room_dims.width_estimate} x {room_dims.height_estimate} (percentage coordinates 0-100)

FIX these specific violations by adjusting object positions. 
- Move objects to avoid overlaps
- Ensure minimum 5% clearance between objects
- Keep all objects within room bounds (0-100)
- Do not change structural objects

Return ONLY the corrected movable objects as JSON array:
[
  {{"id": "object_id", "bbox": [x, y, w, h], "orientation": 0}},
  ...
]
"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            fixes = json.loads(response.text)
            
            # Apply fixes
            if isinstance(fixes, list):
                return self._merge_layout(layout, fixes, [])
            elif isinstance(fixes, dict) and "objects" in fixes:
                return self._merge_layout(layout, fixes["objects"], [])
                
        except Exception:
            pass  # If fix fails, return original layout
            
        return None


async def designer_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node that runs the Designer Agent.
    
    Replaces the deterministic solver_node with LLM-powered generation.
    
    Args:
        state: Current agent state
        
    Returns:
        State updates with layout variations
    """
    designer = InteriorDesignerAgent()
    
    try:
        variations = await designer.generate_layout_variations(
            current_layout=state["current_layout"],
            room_dims=state["room_dimensions"],
            locked_ids=state.get("locked_object_ids", [])
        )
        
        # Store all variations
        # Frontend will display these and let user choose
        return {
            "layout_variations": variations,
            "proposed_layout": variations[0]["layout"] if variations else state["current_layout"],
            "explanation": f"Generated {len(variations)} layout variations using AI design principles.",
            "should_continue": False,  # Designer is a one-shot, no iteration needed
            "iteration_count": state.get("iteration_count", 0) + 1
        }
        
    except Exception as e:
        return {
            "error": f"Designer agent failed: {str(e)}",
            "should_continue": False
        }


def designer_node_sync(state: AgentState) -> Dict[str, Any]:
    """
    Synchronous wrapper for the designer node (for LangGraph compatibility).
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, safe to use asyncio.run()
        return asyncio.run(designer_node(state))
    else:
        # Already in an async context, use nest_asyncio or run in new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, designer_node(state))
            return future.result()
