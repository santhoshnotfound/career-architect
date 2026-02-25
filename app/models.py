# models.py
# ------------------------------------------------------------
# Defines the database tables using SQLAlchemy ORM.
# Each class here maps to one table in career.db.
#
# Tables:
#   skills          — skill node records (original)
#   feedback        — skill extraction feedback (original)
#   users           — registered user accounts (Phase 3)
#   user_profiles   — saved skill selections per user (Phase 3)
#   roadmap_history — append-only log of roadmap runs per user (Phase 3)
# ------------------------------------------------------------

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import relationship
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


# ── Phase 3: User Account Models ─────────────────────────────
# Three new tables added without touching the existing Skill and
# Feedback tables. All new tables are created automatically by
# Base.metadata.create_all() in main.py on startup.


class User(Base):
    """
    Registered user account.

    One User row per email address. The plain-text password is
    NEVER stored — only the bcrypt hash is persisted.

    Relationships:
        profile  — one-to-one UserProfile (None if never saved)
        history  — one-to-many RoadmapHistory (empty list if never generated)
    """
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at      = Column(DateTime, server_default=func.now())

    # ORM relationships — lazy-loaded by default (no extra query unless accessed)
    profile = relationship("UserProfile",    back_populates="user", uselist=False)
    history = relationship("RoadmapHistory", back_populates="user")

    def __repr__(self):
        return f"<User id={self.id} email='{self.email}'>"


class UserProfile(Base):
    """
    Persisted skill selection and role preference for a user.

    One-to-one with User (enforced by unique=True on user_id).
    Created on the first POST /users/save-profile call;
    subsequent calls overwrite the same row.

    Skills are stored as a JSON string: '["Python", "Git"]'
    Always use json.dumps() on write and json.loads() on read.
    """
    __tablename__ = "user_profiles"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    selected_skills = Column(Text, nullable=True)     # json.dumps(list[str])
    target_role     = Column(String(100), nullable=True)
    # Python-side datetime callback — SQLite has no server-side ON UPDATE trigger.
    # Pass the function reference (no parentheses) so SQLAlchemy calls it on each UPDATE.
    last_updated    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")

    def __repr__(self):
        return f"<UserProfile user_id={self.user_id} role='{self.target_role}'>"


class RoadmapHistory(Base):
    """
    Immutable append-only log of roadmap generation events.

    One row is inserted each time an authenticated user calls
    POST /roadmap/. Rows are never updated or deleted.

    readiness_score is nullable: the roadmap endpoint does not
    compute the score (to avoid a redundant graph traversal).
    Users can fetch the score independently via POST /readiness/.

    Skills are stored as JSON strings — same pattern as UserProfile.
    """
    __tablename__ = "roadmap_history"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    role            = Column(String(100), nullable=False)
    known_skills    = Column(Text, nullable=True)    # json.dumps(list[str])
    missing_skills  = Column(Text, nullable=True)    # json.dumps(list[str])
    readiness_score = Column(Integer, nullable=True) # None = not yet computed
    created_at      = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="history")

    def __repr__(self):
        return f"<RoadmapHistory id={self.id} user_id={self.user_id} role='{self.role}'>"
