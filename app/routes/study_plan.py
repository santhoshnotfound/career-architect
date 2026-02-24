# app/routes/study_plan.py
# ============================================================
# HTTP route for the Semester Study Plan endpoint.
# All planning logic lives in app/analytics/planner.py.
# ============================================================

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.analytics.planner import generate_study_plan

router = APIRouter(prefix="/study-plan", tags=["Analytics"])


class StudyPlanRequest(BaseModel):
    user_skills:    list[str] = Field(..., description="Current student skills.")
    target_role:    str       = Field(..., description="Target career role.")
    hours_per_week: int       = Field(6,   ge=1, le=40, description="Study hours per week.")
    months:         int       = Field(3,   ge=1, le=24, description="Months available.")


@router.post(
    "/",
    summary="Generate a semester-by-week study plan",
)
def study_plan(request: StudyPlanRequest):
    """
    Converts the student's skill gap into a week-by-week study schedule.

    Skills are distributed proportionally to their estimated learning effort
    and ordered to respect prerequisite dependencies.

    ### Example Request
    ```json
    {
      "user_skills": ["Python", "Git"],
      "target_role": "AI Researcher",
      "hours_per_week": 8,
      "months": 4
    }
    ```
    """
    try:
        return generate_study_plan(
            user_skills    = request.user_skills,
            target_role    = request.target_role,
            hours_per_week = request.hours_per_week,
            months         = request.months,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
