# main.py
# ------------------------------------------------------------
# Entry point for the Career Architect API.
# This file:
#   1. Creates the FastAPI application instance
#   2. Registers all routers (routes/health.py, routes/skills.py)
#   3. Creates database tables on startup
#   4. Adds CORS middleware for future frontend integration
#
# Run with:
#   uvicorn app.main:app --reload
# ------------------------------------------------------------

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes import health, skills, roadmap, extract, graph_data, readiness, study_plan, report, github_scan, feedback

# ── Create all tables defined in models.py ──────────────────
# This runs once when the server starts. If tables already
# exist, SQLAlchemy skips them (it does NOT drop and recreate).
# For production you would use Alembic migrations instead.
Base.metadata.create_all(bind=engine)

# ── Initialize the FastAPI app ───────────────────────────────
app = FastAPI(
    title="Career Architect API",
    description=(
        "A knowledge-graph based learning roadmap generator. "
        "Maps student skills against industry requirements and "
        "generates prioritized learning paths."
    ),
    version="0.1.0",
)

# ── CORS Middleware ──────────────────────────────────────────
# Allows a frontend (React, plain HTML) running on a different
# port to make requests to this API during development.
# In production, replace "*" with your actual frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],        # Allow GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],
)

# ── Register Routers ─────────────────────────────────────────
# Each router is a self-contained module of related endpoints.
# Adding a new feature = create a new route file + include it here.
app.include_router(health.router)
app.include_router(skills.router)
app.include_router(roadmap.router)       # Knowledge graph + gap analysis
app.include_router(extract.router)       # AI skill extraction from resume text
app.include_router(graph_data.router)    # Graph data for SVG visualization
app.include_router(readiness.router)     # Readiness score engine
app.include_router(study_plan.router)    # Semester learning planner
app.include_router(report.router)        # Academic PDF report generator
app.include_router(github_scan.router)   # GitHub profile scanner
app.include_router(feedback.router)       # Feedback on skill extraction


@app.get("/", include_in_schema=False)
def root():
    """Redirect hint for developers hitting the base URL."""
    return {
        "message": "Career Architect API is running.",
        "docs": "/docs",
        "health": "/health",
    }
