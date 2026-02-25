# app/routes/users.py
# ============================================================
# User profile and roadmap history endpoints.
#
# Why this file exists:
#   Provides the three "logged-in user" endpoints that allow
#   students to persist their skill selections and review their
#   roadmap history across sessions.
#
# All endpoints require a valid JWT (via get_current_user).
# Unauthenticated requests receive HTTP 401.
#
# Endpoints:
#   GET  /users/me            — return current user info + saved profile
#   POST /users/save-profile  — save/update selected skills and role
#   GET  /users/history       — list previous roadmap generation events
#
# Skills are stored as JSON strings in the DB (Text column).
# Serialization (json.dumps) happens in crud.py.
# Deserialization (json.loads) happens here before building schemas.
# ============================================================

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.models import User
from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get(
    "/me",
    response_model=schemas.ProfileRead,
    summary="Get current user account and saved profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the authenticated user's account information and saved profile.

    If the user has never called `POST /users/save-profile`, the
    `selected_skills` list will be empty and `target_role` will be null.

    ### Requires
    `Authorization: Bearer <token>`

    ### Example Response
    ```json
    {
      "id": 1,
      "email": "alice@example.com",
      "created_at": "2024-01-15T10:30:00",
      "selected_skills": ["Python", "Git", "Statistics"],
      "target_role": "Data Scientist",
      "last_updated": "2024-01-15T11:00:00"
    }
    ```
    """
    profile = crud.get_profile(db=db, user_id=current_user.id)

    return schemas.ProfileRead(
        id              = current_user.id,
        email           = current_user.email,
        created_at      = current_user.created_at,
        selected_skills = json.loads(profile.selected_skills or "[]") if profile else [],
        target_role     = profile.target_role if profile else None,
        last_updated    = profile.last_updated if profile else None,
    )


@router.post(
    "/save-profile",
    response_model=schemas.ProfileRead,
    summary="Save or update selected skills and target role",
)
def save_profile(
    body: schemas.ProfileSave,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Persist the user's selected skills and target role.

    Calling this endpoint multiple times **replaces** the previous profile —
    there is only one active profile per user. To update just the role,
    re-send the full skill list alongside the new role.

    ### Requires
    `Authorization: Bearer <token>`

    ### Example Request
    ```json
    {
      "selected_skills": ["Python", "Git", "Statistics"],
      "target_role": "Data Scientist"
    }
    ```
    """
    profile = crud.upsert_profile(
        db              = db,
        user_id         = current_user.id,
        selected_skills = body.selected_skills,
        target_role     = body.target_role,
    )

    return schemas.ProfileRead(
        id              = current_user.id,
        email           = current_user.email,
        created_at      = current_user.created_at,
        selected_skills = json.loads(profile.selected_skills or "[]"),
        target_role     = profile.target_role,
        last_updated    = profile.last_updated,
    )


@router.get(
    "/history",
    response_model=list[schemas.HistoryEntry],
    summary="Get roadmap generation history",
)
def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Maximum number of history entries to return (newest first).",
    ),
):
    """
    Return up to `limit` roadmap generation events for the authenticated user,
    ordered newest-first.

    Each entry records the role targeted, which skills were known and missing
    at the time, and (optionally) the readiness score if it was computed.

    History entries are created automatically every time an authenticated user
    calls `POST /roadmap/` — no extra action is required.

    ### Requires
    `Authorization: Bearer <token>`

    ### Example Response
    ```json
    [
      {
        "id": 3,
        "role": "AI Researcher",
        "known_skills": ["Python", "Git"],
        "missing_skills": ["Linear Algebra", "Machine Learning"],
        "readiness_score": null,
        "created_at": "2024-01-15T11:05:00"
      }
    ]
    ```
    """
    rows = crud.get_user_history(db=db, user_id=current_user.id, limit=limit)

    return [
        schemas.HistoryEntry(
            id              = row.id,
            role            = row.role,
            known_skills    = json.loads(row.known_skills or "[]"),
            missing_skills  = json.loads(row.missing_skills or "[]"),
            readiness_score = row.readiness_score,
            created_at      = row.created_at,
        )
        for row in rows
    ]
