# schemas.py
# ------------------------------------------------------------
# Pydantic schemas define the shape of data going IN and OUT
# of the API. They are separate from SQLAlchemy models because:
#   - API shape ≠ database shape (e.g., you never expose raw IDs
#     or internal fields to the client)
#   - Pydantic handles validation and serialization automatically
#   - This separation makes refactoring much safer
# ------------------------------------------------------------

from pydantic import BaseModel, Field


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
