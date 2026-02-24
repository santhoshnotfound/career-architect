# app/routes/readiness.py
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.analytics.readiness import calculate_readiness

router = APIRouter(prefix="/readiness", tags=["Analytics"])


class ReadinessRequest(BaseModel):
    user_skills: list[str] = Field(..., description="Skills the student currently has.")
    target_role: str       = Field(..., description="Target career role.")


@router.post("/", summary="Compute career readiness score")
def readiness_score(request: ReadinessRequest):
    try:
        return calculate_readiness(request.user_skills, request.target_role)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
