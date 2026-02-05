"""
Agent State

Defines the shared state passed between LangGraph nodes.
This is the "memory" of the agent as it processes a room.

UPGRADED for generative design workflow:
- layout_variations: Multiple layout options from Designer
- output_image_base64: Perspective render output
- edit_command: Chat-based editing commands
"""

from typing import TypedDict, List, Optional, Annotated, Dict, Any
import operator

from app.models.room import RoomObject, RoomDimensions, ConstraintViolation, LayoutScore


class AgentState(TypedDict):
    """
    Shared state for the LangGraph workflow.
    
    This state is passed between nodes and updated at each step.
    Supports both legacy deterministic optimization and new generative design.
    """
    
    # === Input ===
    image_base64: str                           # Original room photo (base64)
    room_dimensions: RoomDimensions             # Room size
    
    # === Layout State ===
    original_layout: List[RoomObject]           # Initial detected layout
    current_layout: List[RoomObject]            # Layout being optimized/edited
    locked_object_ids: List[str]                # User-locked objects
    
    # === Generative Design (NEW) ===
    layout_variations: Optional[List[Dict[str, Any]]]  # 2-3 layout options from Designer
    selected_variation_index: Optional[int]     # Which variation user selected (0, 1, or 2)
    
    # === Constraint Results ===
    constraint_violations: Annotated[List[ConstraintViolation], operator.add]
    
    # === Optimization State ===
    iteration_count: int                        # Current iteration number
    max_iterations: int                         # Maximum iterations allowed
    
    # === Scoring ===
    initial_score: Optional[LayoutScore]        # Score before optimization
    current_score: Optional[LayoutScore]        # Score after optimization
    
    # === Output ===
    proposed_layout: Optional[List[RoomObject]] # Final optimized layout
    explanation: str                            # Human-readable explanation
    output_image_url: Optional[str]             # Rendered result image URL
    output_image_base64: Optional[str]          # Rendered perspective image (NEW)
    
    # === Chat Editing (NEW) ===
    edit_command: Optional[str]                 # Natural language edit command
    edit_history: Optional[List[str]]           # History of edit commands
    
    # === Control ===
    should_continue: bool                       # Whether to keep iterating
    error: Optional[str]                        # Error message if failed


def create_initial_state(
    image_base64: str,
    room_dimensions: RoomDimensions,
    objects: List[RoomObject],
    locked_ids: List[str] = None,
    max_iterations: int = 5
) -> AgentState:
    """
    Create initial agent state from input data.
    
    Args:
        image_base64: Room photo as base64 string
        room_dimensions: Width and height of room
        objects: Detected room objects
        locked_ids: IDs of objects user has locked
        max_iterations: Max optimization iterations
        
    Returns:
        Initial AgentState ready for processing
    """
    return AgentState(
        image_base64=image_base64,
        room_dimensions=room_dimensions,
        original_layout=objects.copy(),
        current_layout=objects.copy(),
        locked_object_ids=locked_ids or [],
        layout_variations=None,
        selected_variation_index=None,
        constraint_violations=[],
        iteration_count=0,
        max_iterations=max_iterations,
        initial_score=None,
        current_score=None,
        proposed_layout=None,
        explanation="",
        output_image_url=None,
        output_image_base64=None,
        edit_command=None,
        edit_history=None,
        should_continue=True,
        error=None
    )

