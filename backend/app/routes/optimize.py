"""
Optimize Route

POST /optimize - Optimize a room layout with AI-powered design variations.
This is the core endpoint that uses our LangGraph workflow.

UPGRADED for generative design:
- Generates 2-3 layout variations using LLM
- Supports legacy single-layout mode for backwards compatibility
"""

import os
import asyncio
from fastapi import APIRouter, HTTPException, Query

from app.models.api import OptimizeRequest, OptimizeResponse, LayoutVariation
from app.models.api import OptimizeRequest, OptimizeResponse, LayoutVariation
from app.agents.designer_node import InteriorDesignerAgent
from app.core.scoring import score_layout

# LangSmith tracing - import for automatic instrumentation
try:
    from langsmith import traceable
    LANGSMITH_ENABLED = True
except ImportError:
    LANGSMITH_ENABLED = False
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


router = APIRouter(prefix="/optimize", tags=["Optimization"])


@router.post("", response_model=OptimizeResponse)
@traceable(name="optimize_layout", run_type="chain")
async def optimize_layout(
    request: OptimizeRequest
) -> OptimizeResponse:
    """
    Optimize a room layout with AI-powered design variations.
    
    This endpoint:
    1. Takes current layout and locked object IDs
    2. Generates 2-3 layout variations using AI
    3. Returns variations with explanations and scores
    
    The AI Designer will generate:
    - Flow Optimized: Maximize walking space
    - Zoned Living: Distinct functional zones  
    - Creative: Bold, unconventional arrangement
    """
    try:
        # Mark locked objects
        for obj in request.current_layout:
            if obj.id in request.locked_ids:
                obj.is_locked = True
        
        # Use AI Designer for variations
        designer = InteriorDesignerAgent()
        variations_data = await designer.generate_layout_variations(
            current_layout=request.current_layout,
            room_dims=request.room_dimensions,
            locked_ids=request.locked_ids,
            image_base64=request.image_base64
        )
        
        # Convert to LayoutVariation models
        variations = []
        for var in variations_data:
            layout_score_obj = score_layout(
                var["layout"],
                int(request.room_dimensions.width_estimate),
                int(request.room_dimensions.height_estimate)
            )
            variations.append(LayoutVariation(
                name=var["name"],
                description=var["description"],
                layout=var["layout"],
                score=layout_score_obj.total_score
            ))
        
        # Get best variation for legacy fields (if needed by frontend)
        best_variation = variations[0] if variations else None
        
        return OptimizeResponse(
            variations=variations,
            message=f"Generated {len(variations)} layout variations using AI design principles.",
            # Legacy fields for backwards compatibility
            new_layout=best_variation.layout if best_variation else request.current_layout,
            explanation=best_variation.description if best_variation else "No variations generated",
            layout_score=best_variation.score if best_variation else 0.0,
            iterations=1,
            constraint_violations=[],
            improvement=0.0
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Optimization failed: {str(e)}"
        )
