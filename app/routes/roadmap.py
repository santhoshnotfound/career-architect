# routes/roadmap.py
# ============================================================
# HTTP routes for the Knowledge Graph Roadmap feature.
#
# This file is intentionally thin. All graph logic lives in
# graph_engine.py. This layer only handles:
#   - Parsing and validating HTTP input (via Pydantic schemas)
#   - Calling the graph engine
#   - Formatting and returning HTTP responses
#   - Converting engine errors into correct HTTP status codes
#
# Phase 3 addition:
#   generate_roadmap() now accepts an optional authenticated user.
#   If a valid JWT is present, the result is saved to RoadmapHistory
#   as a best-effort side-effect. The response shape is UNCHANGED.
#   Unauthenticated requests continue to work exactly as before.
# ============================================================

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.graph_engine import compute_skill_gap, get_graph_summary
from app.database import get_db
from app import crud
from app.models import User
from app.auth.dependencies import get_optional_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/roadmap",
    tags=["Roadmap"],
)


# ── Request / Response Schemas ────────────────────────────────
# These are defined here (not in schemas.py) because they are
# tightly coupled to this route and have no database layer.

class RoadmapRequest(BaseModel):
    """
    Input schema for POST /roadmap.

    The user provides their current skills and the role they
    are targeting. Skill names are matched case-insensitively
    against the graph, so "python" and "Python" both work.
    """
    user_skills: list[str] = Field(
        ...,
        min_length=1,
        description="Skills the student currently has.",
        examples=[["Python", "Git", "Statistics"]],
    )
    target_role: str = Field(
        ...,
        description="The career role to generate a roadmap for.",
        examples=["AI Researcher"],
    )


class RoadmapResponse(BaseModel):
    """
    Output schema for POST /roadmap.

    known_skills   — Required skills the student already has.
    missing_skills — Required skills the student still needs.
    learning_paths — For each missing skill: the ordered sequence
                     of skills to acquire, from current knowledge
                     to the target skill.
    """
    target_role:    str
    known_skills:   list[str]
    missing_skills: list[str]
    learning_paths: dict[str, list[str]]


class GraphInfoResponse(BaseModel):
    """Output schema for GET /roadmap/graph-info."""
    total_nodes:     int
    total_edges:     int
    all_skills:      list[str]
    available_roles: list[str]
    is_dag:          bool


# ── Endpoints ─────────────────────────────────────────────────

@router.post(
    "/",
    response_model=RoadmapResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a personalised learning roadmap",
)
def generate_roadmap(
    request: RoadmapRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Core endpoint. Accepts a student's current skills and a
    target role, then returns:

    - Which required skills they already have (**known_skills**)
    - Which required skills are missing (**missing_skills**)
    - For each missing skill: the shortest prerequisite path
      from their existing knowledge to that skill (**learning_paths**)

    **Auth is optional.** Anonymous calls work exactly as before.
    Authenticated calls (valid `Authorization: Bearer <token>` header)
    additionally save the result to the user's roadmap history —
    visible later via `GET /users/history`.

    ### Example Request
    ```json
    {
      "user_skills": ["Python", "Git"],
      "target_role": "AI Researcher"
    }
    ```

    ### Available Roles
    - `AI Researcher`
    - `Machine Learning Engineer`
    - `Backend Engineer`
    - `Data Scientist`
    """
    try:
        result = compute_skill_gap(
            user_skills=request.user_skills,
            role=request.target_role,
        )
    except ValueError as e:
        # compute_skill_gap raises ValueError for unknown roles.
        # We surface this as HTTP 422 Unprocessable Entity.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    # ── Phase 3: optional history save ───────────────────────────
    # Only runs if the request included a valid bearer token.
    # Wrapped in try/except so a DB failure here never breaks the
    # core roadmap response — history is a best-effort side-effect.
    if current_user is not None:
        try:
            crud.create_history_entry(
                db             = db,
                user_id        = current_user.id,
                role           = request.target_role,
                known_skills   = result["known_skills"],
                missing_skills = result["missing_skills"],
                readiness_score= None,  # computed separately via POST /readiness/
            )
        except Exception:
            logger.warning(
                "Failed to save roadmap history for user %d",
                current_user.id,
                exc_info=True,
            )

    return RoadmapResponse(
        target_role=request.target_role,
        **result,
    )


@router.get(
    "/graph-info",
    response_model=GraphInfoResponse,
    summary="Inspect the knowledge graph structure",
)
def graph_info():
    """
    Returns metadata about the loaded knowledge graph.

    Useful for:
    - Verifying which skills and roles exist
    - Confirming the graph is a valid DAG (no cycles)
    - Debugging skill name mismatches in requests

    This endpoint has no input — it always reflects the
    current state of the in-memory graph.
    """
    return get_graph_summary()
