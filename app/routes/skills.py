# routes/skills.py
# ------------------------------------------------------------
# All HTTP routes related to Skills.
# Routes are thin: they handle HTTP concerns only
# (parsing input, returning correct status codes, error messages).
# All database logic lives in crud.py.
# ------------------------------------------------------------

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(
    prefix="/skills",   # All routes here are under /skills
    tags=["Skills"],    # Groups these endpoints in the API docs
)


@router.post(
    "/",
    response_model=schemas.SkillRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new skill",
)
def create_skill(skill: schemas.SkillCreate, db: Session = Depends(get_db)):
    """
    Add a new skill to the knowledge graph.

    - **name**: Must be unique. Duplicate names return HTTP 409.

    Example request body:
    ```json
    { "name": "Python" }
    ```
    """
    try:
        return crud.create_skill(db=db, skill=skill)
    except ValueError as e:
        # crud.create_skill raises ValueError on duplicate names.
        # We convert that into a proper HTTP 409 Conflict response.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "/",
    response_model=list[schemas.SkillRead],
    summary="List all skills",
)
def list_skills(db: Session = Depends(get_db)):
    """
    Retrieve all skills currently in the knowledge graph.

    Returns an empty list if no skills have been added yet.
    Skills are returned in alphabetical order by name.
    """
    return crud.get_all_skills(db=db)
