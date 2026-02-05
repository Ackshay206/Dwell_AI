# Pocket Planner - Complete Build Guide for Antigravity IDE

Master Refactoring Prompt: Pocket Planner 2.0 → Generative 3D Interior Design System
Context

Role: You are a Senior Full-Stack Architect and AI Engineer.
Context: We are refactoring an existing project ("Pocket Planner") which currently uses simple heuristic logic and 2D bounding boxes.
Goal: Transform this into a "Generative Interior Design Agent" that understands 3D top-down floor plans, uses LLMs for layout optimization, generates photorealistic perspective views, and supports conversational image editing.



You are refactoring the Pocket Planner repository located at https://github.com/Ackshay206/pocket-planner. The current system uses:

Backend: FastAPI, LangGraph, Gemini 2.5 Flash, Shapely geometry

Frontend: Next.js 14, TypeScript, React-Konva

Current Architecture: 3-node LangGraph workflow (Vision → Constraint → Solver)

Current Behavior: Deterministic spatial optimization using Python geometry helpers

Transformation Goal
Convert from a 2D deterministic system into a generative 3D-aware interior design agent that:

Accepts 2D top-down images of 3D floor plans

Generates 2-3 semantically meaningful layout variations using LLM reasoning

Creates photorealistic 2D side-view renders

Supports conversational surgical editing of the final render

Phase 1: Data Schema & Vision Upgrade
1.1 Update Data Models (backend/app/models/room.py)
Current State:

RoomObject has: id, label, bbox (4 ints), type, orientation (0-360), is_locked

bbox is [x, y, width, height] in pixels

Required Changes:

python
class RoomObject(BaseModel):
    id: str
    label: str
    bbox: List[int] = Field(..., min_length=4, max_length=4)
    type: ObjectType
    orientation: int = Field(default=0, ge=0, lt=360)  # KEEP THIS - critical for top-down plans
    is_locked: bool = Field(default=False)
    
    # NEW FIELDS:
    z_index: int = Field(default=1, description="0=floor/rugs, 1=furniture, 2=ceiling")
    material_hint: Optional[str] = Field(None, description="e.g., 'wooden', 'fabric', 'glass'")
    footprint_polygon: Optional[List[Tuple[float, float]]] = Field(
        None, 
        description="Optional precise polygon for L-shaped/curved objects"
    )
Why: Top-down 3D floor plans need depth ordering (z_index) and material context for realistic rendering. footprint_polygon is optional for complex shapes but start with bounding boxes.

1.2 Upgrade Vision Agent (backend/app/agents/vision_node.py)
Current State:

Uses gemini-2.5-flash

Extracts bbox as [x_percent, y_percent, w_percent, h_percent]

Returns AnalyzeResponse with room_dimensions and objects

Required Changes:

python
class VisionExtractor:
    def __init__(self):
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.0-flash"  # UPGRADE: Better spatial reasoning
    
    async def extract_objects(self, image_base64: str, max_retries: int = 3) -> AnalyzeResponse:
        prompt = """You are an expert Architectural Computer Vision agent.
        
        Analyze this TOP-DOWN 3D FLOOR PLAN image.
        
        CRITICAL: This is a bird's-eye view of a room. Extract the "footprint" of each object 
        (where it touches the floor), not just the visible top surface.
        
        Return JSON with this EXACT schema:
        {
          "room_dimensions": {"width": float, "height": float},  // Estimate in feet
          "objects": [
            {
              "id": "label_N",
              "label": "bed|desk|chair|door|window|wall|rug|dresser|nightstand",
              "bbox": [x_pct, y_pct, w_pct, h_pct],  // 0-100 relative to image
              "type": "movable|structural",
              "orientation": int,  // 0=North, 90=East, 180=South, 270=West
              "z_index": int,  // 0=floor, 1=furniture, 2=ceiling
              "material_hint": "wooden|fabric|metal|glass|null"
            }
          ]
        }
        
        Rules:
        - Doors/windows are STRUCTURAL (type="structural")
        - Furniture is MOVABLE (type="movable")
        - Orientation MUST reflect which direction the object "faces" (e.g., bed headboard direction)
        """
        
        # ... rest of your existing Gemini call logic ...
        # IMPORTANT: Parse and validate the new fields (z_index, orientation, material_hint)
Test: Upload a top-down floor plan and verify that orientation is correctly detected (e.g., bed facing different walls).

Phase 2: The LLM-Powered Designer Agent
2.1 Create New Agent (backend/app/agents/designer_node.py)
Purpose: Replace the deterministic solver_node.py logic with LLM-driven semantic layout generation.

python
"""
Designer Node (The "Architect Brain")

Generates 2-3 distinct, architecturally sound layout variations using LLM reasoning.
Validation still uses Python (ConstraintEngine), but generation is semantic.
"""

import os
import json
from google import genai
from google.genai import types
from typing import List, Dict, Any
from app.models.state import AgentState
from app.models.room import RoomObject, RoomDimensions
from app.core.constraints import check_all_hard_constraints
from app.core.geometry import bbox_to_polygon, check_overlap

class InteriorDesignerAgent:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        self.model = "gemini-1.5-pro"  # Stronger reasoning model
    
    async def generate_layout_variations(
        self, 
        current_layout: List[RoomObject],
        room_dims: RoomDimensions,
        locked_ids: List[str],
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generate 3 distinct layout options using LLM reasoning.
        
        Returns:
            List of 3 dictionaries with keys: "name", "description", "layout" (List[RoomObject])
        """
        
        # Prepare input for LLM
        movable_objects = [
            {
                "id": obj.id,
                "label": obj.label,
                "bbox": obj.bbox,
                "orientation": obj.orientation,
                "is_locked": obj.id in locked_ids
            }
            for obj in current_layout if obj.id not in locked_ids
        ]
        
        structural_objects = [
            {"id": obj.id, "label": obj.label, "bbox": obj.bbox}
            for obj in current_layout if obj.id in locked_ids or obj.type == ObjectType.STRUCTURAL
        ]
        
        prompt = f"""You are a Master Interior Architect.

Room Dimensions: {room_dims.width_estimate} x {room_dims.height_estimate} feet.

STRUCTURAL ELEMENTS (FIXED - DO NOT MOVE):
{json.dumps(structural_objects, indent=2)}

MOVABLE FURNITURE:
{json.dumps(movable_objects, indent=2)}

YOUR TASK: Generate 3 DISTINCT layout variations. Each must be:
1. VALID (no overlaps, minimum 3ft clearance between furniture)
2. FUNCTIONAL (doors unblocked, logical flow)
3. ARCHITECTURALLY MEANINGFUL (not random)

LAYOUT THEMES:
- Option A: "Flow Optimized" - Maximize walking space and circulation
- Option B: "Zoned Living" - Distinct functional zones (sleep, work, relax)
- Option C: "Creative/Unconventional" - Bold, artistic arrangement

CRITICAL RULES:
- NEVER move structural objects (doors, windows, walls)
- NEVER overlap objects (minimum 6 inches clearance)
- Ensure 3ft clearance in front of doors
- Consider "orientation" - don't place a bed facing a wall

OUTPUT JSON SCHEMA:
{{
  "variations": [
    {{
      "name": "Flow Optimized",
      "description": "Brief explanation of design rationale",
      "objects": [
        {{
          "id": "bed_1",
          "bbox": [new_x, new_y, width, height],  // NEW coordinates in feet
          "orientation": 0  // NEW orientation if changed
        }},
        ...
      ]
    }},
    {{
      "name": "Zoned Living",
      ...
    }},
    {{
      "name": "Creative",
      ...
    }}
  ]
}}

Return ONLY valid JSON. No markdown, no explanations outside JSON.
"""
        
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                
                data = json.loads(response.text)
                variations = []
                
                for var in data.get("variations", []):
                    # Merge LLM output with original objects
                    new_layout = self._merge_layout(current_layout, var["objects"])
                    
                    # VALIDATE with ConstraintEngine
                    violations = check_all_hard_constraints(
                        new_layout,
                        room_dims.width_estimate,
                        room_dims.height_estimate
                    )
                    
                    if violations:
                        # Feedback loop: Ask LLM to fix specific violations
                        new_layout = await self._fix_violations(
                            new_layout, violations, room_dims
                        )
                    
                    variations.append({
                        "name": var["name"],
                        "description": var["description"],
                        "layout": new_layout
                    })
                
                return variations[:3]  # Return top 3
                
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"Designer failed after {max_retries} attempts: {e}")
    
    def _merge_layout(
        self, 
        original: List[RoomObject], 
        llm_updates: List[dict]
    ) -> List[RoomObject]:
        """Merge LLM's updated positions with original object data."""
        updated_map = {obj["id"]: obj for obj in llm_updates}
        new_layout = []
        
        for obj in original:
            if obj.id in updated_map:
                # Update position from LLM
                llm_obj = updated_map[obj.id]
                obj.bbox = llm_obj["bbox"]
                obj.orientation = llm_obj.get("orientation", obj.orientation)
            new_layout.append(obj.model_copy())
        
        return new_layout
    
    async def _fix_violations(
        self, 
        layout: List[RoomObject], 
        violations: List, 
        room_dims: RoomDimensions
    ) -> List[RoomObject]:
        """Ask LLM to fix specific constraint violations (feedback loop)."""
        violation_desc = "\n".join([f"- {v.description}" for v in violations])
        
        prompt = f"""The layout you generated has these ERRORS:
{violation_desc}

Original layout JSON:
{json.dumps([{"id": o.id, "bbox": o.bbox} for o in layout], indent=2)}

FIX these specific violations by adjusting object positions. Return ONLY the corrected objects as JSON.
"""
        # ... call LLM again, parse, return fixed layout ...
        # (Implementation similar to generate_layout_variations)
2.2 Update API Response Schema (backend/app/models/api.py)
Current:

python
class OptimizeResponse(BaseModel):
    new_layout: List[RoomObject]
    explanation: str
    layout_score: float
    ...
New:

python
class LayoutVariation(BaseModel):
    """A single layout option."""
    name: str = Field(..., description="e.g., 'Flow Optimized'")
    description: str = Field(..., description="Design rationale")
    layout: List[RoomObject]
    thumbnail_base64: Optional[str] = Field(None, description="Preview render")

class OptimizeResponse(BaseModel):
    """Response with 2-3 layout options."""
    variations: List[LayoutVariation] = Field(..., min_items=2, max_items=3)
    message: str = "Generated layout variations"
2.3 Update LangGraph Workflow (backend/app/agents/graph.py)
Current Flow:

text
Vision → Constraint → Solver ←→ Constraint → Render → END
New Flow:

text
Vision → Designer (LLM) → User Selects → Perspective Generator → Chat Editor → END
Implementation:

python
def create_optimization_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    
    # Nodes
    graph.add_node("vision", vision_node_updated)
    graph.add_node("designer", designer_node)  # NEW: Replaces solver
    graph.add_node("perspective", perspective_node)  # NEW: Generate side view
    graph.add_node("chat_editor", chat_editor_node)  # NEW: Conversational editing
    
    # Edges
    graph.set_entry_point("vision")
    graph.add_edge("vision", "designer")
    
    # Designer outputs 3 options → Frontend displays → User selects one
    # (This requires a PAUSE for user input - use LangGraph's interrupt feature)
    graph.add_edge("designer", "perspective")
    graph.add_edge("perspective", "chat_editor")
    graph.add_edge("chat_editor", END)
    
    return graph
Note: You'll need to handle the "user selection" step. Options:

Frontend-driven: Designer endpoint returns 3 options → Frontend displays → User clicks one → New API call for perspective

LangGraph Human-in-Loop: Use interrupt_before=["perspective"] to pause workflow

Phase 3: Perspective Generation
3.1 Create Perspective Agent (backend/app/agents/perspective_node.py)
python
"""
Perspective Generator

Converts top-down layout JSON → Photorealistic 2D side-view image.
"""

import os
import base64
from google import genai
from google.genai import types
from app.models.room import RoomObject, RoomDimensions

class PerspectiveGenerator:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        self.model = "gemini-2.5-flash-image"
    
    async def generate_side_view(
        self, 
        layout: List[RoomObject],
        room_dims: RoomDimensions,
        style: str = "modern"
    ) -> str:
        """
        Generate a photorealistic eye-level view