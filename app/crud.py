# crud.py
# ------------------------------------------------------------
# CRUD = Create, Read, Update, Delete
# This file contains all direct database operations.
#
# Why separate from routes?
#   - Routes handle HTTP logic (status codes, request parsing)
#   - CRUD handles data logic (queries, inserts, constraints)
#   - This separation makes testing and reuse much easier.
#     You can call these functions from tests, scripts, or
#     other routes without touching HTTP logic.
#
# Original functions: create_skill, get_all_skills
# Phase 3 functions (appended below):
#   Users:   create_user, get_user_by_email, get_user_by_id
#   Profile: upsert_profile, get_profile
#   History: create_history_entry, get_user_history
# ------------------------------------------------------------

import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app import models, schemas


def create_skill(db: Session, skill: schemas.SkillCreate) -> models.Skill:
    """
    Insert a new skill into the database.

    Args:
        db:    The active database session (injected by FastAPI).
        skill: A validated SkillCreate schema from the request body.

    Returns:
        The newly created Skill ORM object, including its auto-assigned ID.

    Raises:
        ValueError: If a skill with the same name already exists.
                    The route layer catches this and returns HTTP 409.
    """
    db_skill = models.Skill(name=skill.name)
    db.add(db_skill)

    try:
        db.commit()
        db.refresh(db_skill)  # Reload from DB to get the auto-generated ID
    except IntegrityError:
        db.rollback()  # Undo the failed insert to keep the session clean
        raise ValueError(f"Skill '{skill.name}' already exists.")

    return db_skill


def get_all_skills(db: Session) -> list[models.Skill]:
    """
    Retrieve all skills from the database, ordered by name.

    Args:
        db: The active database session.

    Returns:
        A list of Skill ORM objects (may be empty if no skills exist yet).
    """
    return db.query(models.Skill).order_by(models.Skill.name).all()


# ── Phase 3: User CRUD ────────────────────────────────────────

def create_user(db: Session, email: str, hashed_password: str) -> models.User:
    """
    Insert a new user record into the database.

    The password must already be hashed before calling this function.
    Never pass a plain-text password here.

    Args:
        db:              Active database session.
        email:           Validated, lowercased email address.
        hashed_password: bcrypt hash from auth.security.hash_password().

    Returns:
        The newly created User ORM object with auto-assigned id.

    Raises:
        ValueError: If the email is already registered.
                    The route layer converts this to HTTP 409.
    """
    user = models.User(email=email, hashed_password=hashed_password)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise ValueError(f"Email '{email}' is already registered.")
    return user


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """
    Look up a user by email address.

    Returns the User ORM object or None if not found.
    Used by the login endpoint to fetch the user for password verification.
    """
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    """
    Look up a user by primary key.

    Returns the User ORM object or None if not found.
    Provided for future use (e.g. admin endpoints, token refresh).
    """
    return db.query(models.User).filter(models.User.id == user_id).first()


# ── Phase 3: Profile CRUD ─────────────────────────────────────

def upsert_profile(
    db: Session,
    user_id: int,
    selected_skills: list[str],
    target_role: Optional[str],
) -> models.UserProfile:
    """
    Create or update the user's profile (upsert).

    Uses a SELECT-then-INSERT-or-UPDATE pattern rather than
    ON CONFLICT syntax, which differs between SQLite and PostgreSQL.
    This approach is portable and safe under SQLite's single-writer model.

    Skills are JSON-serialized before storage. Always deserialize
    with json.loads(profile.selected_skills or "[]") when reading back.

    Args:
        db:              Active database session.
        user_id:         The authenticated user's primary key.
        selected_skills: List of canonical skill names to save.
        target_role:     Target career role string, or None.

    Returns:
        The created or updated UserProfile ORM object.
    """
    profile = db.query(models.UserProfile).filter(
        models.UserProfile.user_id == user_id
    ).first()

    now = datetime.utcnow()
    if profile is None:
        # First time saving — create a new profile row
        profile = models.UserProfile(
            user_id         = user_id,
            selected_skills = json.dumps(selected_skills),
            target_role     = target_role,
            last_updated    = now,
        )
        db.add(profile)
    else:
        # Profile already exists — overwrite in place
        profile.selected_skills = json.dumps(selected_skills)
        profile.target_role     = target_role
        profile.last_updated    = now

    db.commit()
    db.refresh(profile)
    return profile


def get_profile(db: Session, user_id: int) -> Optional[models.UserProfile]:
    """
    Return the user's saved profile, or None if they have never saved one.

    The route is responsible for deserializing selected_skills from
    JSON string to list[str] before returning to the client.
    """
    return db.query(models.UserProfile).filter(
        models.UserProfile.user_id == user_id
    ).first()


# ── Phase 3: History CRUD ─────────────────────────────────────

def create_history_entry(
    db: Session,
    user_id: int,
    role: str,
    known_skills: list[str],
    missing_skills: list[str],
    readiness_score: Optional[int] = None,
) -> models.RoadmapHistory:
    """
    Append a new roadmap run to the user's history (append-only).

    Always inserts a new row. Never updates an existing one.
    Called automatically from POST /roadmap/ when the user is authenticated.

    Args:
        db:              Active database session.
        user_id:         Authenticated user's primary key.
        role:            Target role string from the roadmap request.
        known_skills:    List of skills the user already had at run time.
        missing_skills:  List of skills the user was still missing.
        readiness_score: Optional pre-computed score (usually None — see model docstring).

    Returns:
        The newly created RoadmapHistory ORM object.
    """
    entry = models.RoadmapHistory(
        user_id         = user_id,
        role            = role,
        known_skills    = json.dumps(known_skills),
        missing_skills  = json.dumps(missing_skills),
        readiness_score = readiness_score,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_user_history(
    db: Session,
    user_id: int,
    limit: int = 20,
) -> list[models.RoadmapHistory]:
    """
    Return the N most recent roadmap history entries for a user.

    Results are ordered newest-first (created_at DESC).
    The default limit of 20 prevents unbounded response payloads;
    the caller can pass a higher limit (up to the route's max of 100).

    The route is responsible for deserializing JSON skill strings
    into lists before constructing the HistoryEntry schemas.
    """
    return (
        db.query(models.RoadmapHistory)
        .filter(models.RoadmapHistory.user_id == user_id)
        .order_by(models.RoadmapHistory.created_at.desc())
        .limit(limit)
        .all()
    )
