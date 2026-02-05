# app/agents/graph.py

import os
import asyncio
from typing import Literal, Dict, Any
from langgraph.graph import StateGraph, END

from app.models.state import AgentState, create_initial_state
from app.models.room import RoomObject, RoomDimensions
from app.agents.designer_node import designer_node_sync
from app.agents.perspective_node import perspective_node_sync
from app.agents.chat_editor_node import chat_editor_node_sync


# LangSmith tracing is automatically enabled when these env vars are set
# No additional code needed - LangGraph integrates with LangSmith automatically


# ============ Vision Node (Upgraded) ============

def vision_node(state: AgentState) -> dict:
    """
    Vision Node - Placeholder that assumes vision extraction is done.
    
    The actual VisionExtractor is called from the API endpoint before
    the graph is invoked, as it requires async image processing.
    
    This node validates the vision output and prepares for the designer.
    """
    # Validate we have required data
    if not state.get("current_layout"):
        return {
            "error": "No layout data from vision extraction",
            "should_continue": False
        }
    
    return {
        "explanation": "Vision analysis complete. Room layout extracted.",
        "should_continue": True
    }


# ============ Render Node (Upgraded) ============

def render_node(state: AgentState) -> dict:
    """
    Render Node - Wrapper for perspective generation.
    
    For synchronous LangGraph execution, wraps the async perspective generator.
    """
    return perspective_node_sync(state)


# ============ Router Functions ============

def should_continue_optimization(state: AgentState) -> Literal["designer", "render"]:
    """
    Decide whether to generate new layouts or render results.
    
    In the new generative flow, we typically go straight to designer
    unless we already have layout variations.
    """
    if state.get("layout_variations"):
        return "render"
    if state.get("should_continue", True):
        return "designer"
    return "render"


def check_for_errors(state: AgentState) -> Literal["designer", "error"]:
    """Check if there's an error in the state."""
    if state.get("error"):
        return "error"
    return "designer"


def should_continue_editing(state: AgentState) -> Literal["render", "end"]:
    """Decide if we need to re-render after chat edits."""
    if state.get("edit_command") and state.get("should_continue", False):
        return "render"
    return "end"


# ============ Graph Definitions ============

def create_optimization_graph() -> StateGraph:
    """
    Create the NEW generative design LangGraph workflow.
    
    New Flow:
        START → vision → designer → render → END
        
    The designer generates 2-3 layout variations.
    Frontend displays options, user selects one.
    Selected layout triggers render for perspective view.
    """
    # Create graph with AgentState
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("vision", vision_node)
    graph.add_node("designer", designer_node_sync)
    graph.add_node("render", render_node)
    
    # Define edges - simple linear flow for now
    graph.set_entry_point("vision")
    graph.add_edge("vision", "designer")
    graph.add_edge("designer", "render")
    graph.add_edge("render", END)
    
    return graph


def create_editing_graph() -> StateGraph:
    """
    Create a graph for conversational editing workflow.
    
    Flow:
        START → chat_editor → (render if needed) → END
    """
    graph = StateGraph(AgentState)
    
    graph.add_node("chat_editor", chat_editor_node_sync)
    graph.add_node("render", render_node)
    
    graph.set_entry_point("chat_editor")
    
    graph.add_conditional_edges(
        "chat_editor",
        should_continue_editing,
        {"render": "render", "end": END}
    )
    
    graph.add_edge("render", END)
    
    return graph


def compile_graph():
    """
    Compile the optimization graph for execution.
    """
    graph = create_optimization_graph()
    return graph.compile()


def compile_editing_graph():
    """Compile the editing graph for chat-based modifications."""
    graph = create_editing_graph()
    return graph.compile()



# ============ Execution Helpers ============

def run_optimization(
    objects: list[RoomObject],
    room_width: int,
    room_height: int,
    locked_ids: list[str] = None,
    image_base64: str = "",
    max_iterations: int = 5
) -> AgentState:
    """
    Run the full optimization workflow.
    
    Args:
        objects: Detected room objects
        room_width: Room width in units
        room_height: Room height in units
        locked_ids: IDs of user-locked objects
        image_base64: Original room image (base64)
        max_iterations: Maximum optimization iterations
        
    Returns:
        Final AgentState with optimized layout
    """
    # Create initial state
    room_dims = RoomDimensions(
        width_estimate=room_width,
        height_estimate=room_height
    )
    
    initial_state = create_initial_state(
        image_base64=image_base64,
        room_dimensions=room_dims,
        objects=objects,
        locked_ids=locked_ids,
        max_iterations=max_iterations
    )
    
    # Compile and run graph
    app = compile_graph()
    
    # Execute
    final_state = app.invoke(initial_state)
    
    return final_state


def run_optimization_stream(
    objects: list[RoomObject],
    room_width: int,
    room_height: int,
    locked_ids: list[str] = None,
    image_base64: str = "",
    max_iterations: int = 5
):
    """
    Run optimization with streaming updates.
    
    Yields state updates as the workflow progresses.
    """
    room_dims = RoomDimensions(
        width_estimate=room_width,
        height_estimate=room_height
    )
    
    initial_state = create_initial_state(
        image_base64=image_base64,
        room_dimensions=room_dims,
        objects=objects,
        locked_ids=locked_ids,
        max_iterations=max_iterations
    )
    
    app = compile_graph()
    
    for step in app.stream(initial_state):
        yield step
