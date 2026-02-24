# models.py
# ------------------------------------------------------------
# Defines the database tables using SQLAlchemy ORM.
# Each class here maps to one table in career.db.
# ------------------------------------------------------------

from sqlalchemy import Column, Integer, String, DateTime, Text, func
from app.database import Base


class Skill(Base):
    """Skill node in the knowledge graph."""
    __tablename__ = "skills"
    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)

    def __repr__(self):
        return f"<Skill id={self.id} name='{self.name}'>"


class Feedback(Base):
    """
    Stores user feedback on skill extraction accuracy.

    Collected when the user clicks 👍 / 👎 after seeing their
    detected skills on Page 2. Used to improve the keyword
    matcher over time by showing which resumes produce wrong results.

    Columns:
        id             — auto-incremented primary key
        rating         — "good" | "bad"
        resume_snippet — first 500 chars of the resume text (for context)
        detected_skills — comma-separated list of what the extractor found
        correct_skills  — what the user said it should have found (optional)
        target_role    — which role the user was targeting
        created_at     — UTC timestamp of when feedback was submitted
    """
    __tablename__ = "feedback"

    id              = Column(Integer, primary_key=True, index=True)
    rating          = Column(String(10), nullable=False)          # "good" | "bad"
    resume_snippet  = Column(Text, nullable=True)                  # first 500 chars
    detected_skills = Column(Text, nullable=True)                  # "Python,Git,ML"
    correct_skills  = Column(Text, nullable=True)                  # user correction
    target_role     = Column(String(100), nullable=True)
    source          = Column(String(20), nullable=True)            # "resume" | "github"
    created_at      = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Feedback id={self.id} rating='{self.rating}'>"
