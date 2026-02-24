# app/routes/report.py
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
import io

from app.analytics.report import generate_report_pdf
from app.graph_engine import TARGET_ROLES

router = APIRouter(prefix="/report", tags=["Analytics"])


@router.get("/", summary="Download academic PDF evaluation report", response_class=StreamingResponse)
def download_report(
    user_skills:    str = Query(..., description="Comma-separated skills, e.g. 'Python,Git'"),
    target_role:    str = Query(..., description="Target role, e.g. 'AI Researcher'"),
    student_name:   str = Query("Student"),
    hours_per_week: int = Query(6,  ge=1, le=40),
    months:         int = Query(3,  ge=1, le=24),
):
    skills = [s.strip() for s in user_skills.split(",") if s.strip()]
    if not skills:
        raise HTTPException(status_code=422, detail="user_skills must not be empty")
    if target_role not in TARGET_ROLES:
        raise HTTPException(status_code=422, detail=f"Unknown role: {target_role}")

    try:
        pdf_bytes = generate_report_pdf(
            user_skills=skills, target_role=target_role,
            student_name=student_name, hours_per_week=hours_per_week, months=months,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

    safe_name = student_name.replace(" ", "_")
    safe_role = target_role.replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=career_report_{safe_name}_{safe_role}.pdf"},
    )
