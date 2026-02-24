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
# ------------------------------------------------------------

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
