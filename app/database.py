# database.py
# ------------------------------------------------------------
# Responsible for all database connection logic.
# Currently uses SQLite (career.db) for local development.
# To switch to PostgreSQL later, only the DATABASE_URL
# constant needs to change — everything else stays the same.
# ------------------------------------------------------------

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite URL format: sqlite:///./filename.db
# The "./" means the file is created in the working directory.
DATABASE_URL = "sqlite:///./career.db"

# The engine is the core interface to the database.
# connect_args is SQLite-specific: it allows the same connection
# to be used across multiple threads (needed for FastAPI).
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# SessionLocal is a factory: each call creates a new database session.
# autocommit=False means we manually control when data is saved.
# autoflush=False means SQLAlchemy won't auto-sync before every query.
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# Base is the parent class for all ORM models.
# Any class that inherits from Base becomes a database table.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Usage in a route:
        def my_route(db: Session = Depends(get_db)):
            ...

    The 'finally' block ensures the session is always closed,
    even if an error occurs mid-request. This prevents connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
