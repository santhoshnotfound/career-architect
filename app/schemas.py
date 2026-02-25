# schemas.py
# ------------------------------------------------------------
# Pydantic schemas define the shape of data going IN and OUT
# of the API. They are separate from SQLAlchemy models because:
#   - API shape ≠ database shape (e.g., you never expose raw IDs
#     or internal fields to the client)
#   - Pydantic handles validation and serialization automatically
#   - This separation makes refactoring much safer
#
# Original schemas: SkillCreate, SkillRead
# Phase 3 schemas (appended below):
#   Auth:    UserRegister, UserLogin, TokenResponse
#   User:    ProfileSave, ProfileRead
#   History: HistoryEntry
# ------------------------------------------------------------

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field


class SkillCreate(BaseModel):
    """
    Schema for creating a new skill.
    Used as the request body for POST /skills.

    Only 'name' is required from the client.
    The database assigns the ID automatically.
    """

    name: str = Field(
        ...,                          # '...' means required, no default
        min_length=1,
        max_length=100,
        description="The name of the skill (e.g., 'Python', 'Linear Algebra')",
        examples=["Python", "Linear Algebra", "PyTorch"],
    )


class SkillRead(BaseModel):
    """
    Schema for reading/returning a skill to the client.
    Used as the response model for GET /skills and POST /skills.

    Includes 'id' because the client needs it for future
    operations (e.g., linking skills as prerequisites).
    """

    id: int
    name: str

    # model_config tells Pydantic to read data from ORM objects
    # (SQLAlchemy model instances), not just plain dictionaries.
    # Without this, returning a Skill ORM object would fail.
    model_config = {"from_attributes": True}


# ── Phase 3: Auth Schemas ─────────────────────────────────────

class UserRegister(BaseModel):
    """
    Request body for POST /auth/register.

    email    — must be a valid email format (validated by EmailStr).
               Used as the unique login identifier.
    password — plain-text; min 8 characters.
               Hashed with bcrypt before storage — never persisted raw.
    """
    email:    EmailStr = Field(..., description="Valid email address.")
    password: str      = Field(..., min_length=8, description="Password (min 8 characters).")


class UserLogin(BaseModel):
    """
    Request body for POST /auth/login.
    Same fields as UserRegister — kept separate so they can diverge
    in the future (e.g. login could add remember_me, device info, etc.)
    """
    email:    EmailStr = Field(..., description="Registered email address.")
    password: str      = Field(..., description="Account password.")


class TokenResponse(BaseModel):
    """
    Response from POST /auth/register and POST /auth/login.
    The client should store access_token and send it as:
        Authorization: Bearer <access_token>
    """
    access_token: str
    token_type:   str = "bearer"


# ── Phase 3: User Profile Schemas ────────────────────────────

class ProfileSave(BaseModel):
    """
    Request body for POST /users/save-profile.
    Replaces the entire profile on each call (no partial update).
    """
    selected_skills: List[str]      = Field(default_factory=list, description="Canonical skill names.")
    target_role:     Optional[str]  = Field(None, description="Target career role.")


class ProfileRead(BaseModel):
    """
    Response from GET /users/me and POST /users/save-profile.

    Manually assembled from User + UserProfile ORM objects in the
    route handler (not auto-converted from ORM), because the fields
    come from two different tables.
    """
    id:              int
    email:           str
    created_at:      datetime
    selected_skills: List[str]           = Field(default_factory=list)
    target_role:     Optional[str]       = None
    last_updated:    Optional[datetime]  = None

    model_config = {"from_attributes": True}


# ── Phase 3: Roadmap History Schema ──────────────────────────

class HistoryEntry(BaseModel):
    """
    One roadmap generation event from GET /users/history.

    known_skills / missing_skills are deserialized from JSON strings
    in the route handler before constructing this schema.

    readiness_score is None when the roadmap was generated without
    also calling POST /readiness/ (the common case).
    """
    id:              int
    role:            str
    known_skills:    List[str]
    missing_skills:  List[str]
    readiness_score: Optional[int]
    created_at:      datetime

    model_config = {"from_attributes": True}
