# app/routes/feedback.py
# ============================================================
# Feedback endpoint — thumbs up/down on skill extraction.
#
# Called from Page 2 (Skill Review) after the user sees their
# detected skills. Stores rating + context in SQLite.
#
# POST /feedback/          — submit a rating
# GET  /feedback/summary   — aggregate stats (for debugging)
# ============================================================

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Feedback

router = APIRouter(prefix="/feedback", tags=["Feedback"])


# ── Request / Response Schemas ────────────────────────────────

class FeedbackRequest(BaseModel):
    rating:          str   = Field(..., pattern="^(good|bad)$")
    detected_skills: list[str]
    resume_snippet:  Optional[str] = None      # first 500 chars of resume
    correct_skills:  Optional[list[str]] = None  # what user says it should be
    target_role:     Optional[str] = None
    source:          Optional[str] = "resume"  # "resume" | "github"

class FeedbackResponse(BaseModel):
    id:      int
    rating:  str
    message: str

class FeedbackSummary(BaseModel):
    total:     int
    good:      int
    bad:       int
    good_pct:  float


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/", response_model=FeedbackResponse, status_code=201,
             summary="Submit skill extraction feedback")
def submit_feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    """
    Record whether the skill extraction result was accurate.

    Called automatically when the user clicks 👍 or 👎 on
    the Skill Review page. No auth required — anonymous feedback.

    The `correct_skills` field is populated only when the user
    clicks 👎 and then edits their skill list, giving us a
    concrete example of what the extractor got wrong.
    """
    row = Feedback(
        rating          = req.rating,
        detected_skills = ",".join(req.detected_skills),
        resume_snippet  = (req.resume_snippet or "")[:500],
        correct_skills  = ",".join(req.correct_skills) if req.correct_skills else None,
        target_role     = req.target_role,
        source          = req.source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return FeedbackResponse(
        id      = row.id,
        rating  = row.rating,
        message = "Thanks for your feedback! It helps improve the skill detector.",
    )


@router.get("/summary", response_model=FeedbackSummary,
            summary="Get aggregate feedback stats")
def feedback_summary(db: Session = Depends(get_db)):
    """
    Returns aggregate counts of good vs bad ratings.
    Useful for monitoring extraction quality over time.
    """
    all_rows = db.query(Feedback).all()
    total    = len(all_rows)
    good     = sum(1 for r in all_rows if r.rating == "good")
    bad      = total - good
    return FeedbackSummary(
        total    = total,
        good     = good,
        bad      = bad,
        good_pct = round(good / total * 100, 1) if total > 0 else 0.0,
    )
