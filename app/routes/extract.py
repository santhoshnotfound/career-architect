# app/routes/extract.py
# ============================================================
# HTTP endpoint for AI-powered skill extraction.
#
# This route is the entry point into the full analysis pipeline:
#   1. User pastes resume text → POST /extract-skills
#   2. AI extracts skill names → returns list
#   3. Frontend sends those skills → POST /roadmap
#   4. Graph engine computes gaps and learning paths
#
# This file only handles HTTP. All AI logic is in:
#   app/ai/skill_extractor.py
# ============================================================

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.ai.skill_extractor import extract_skills_from_text, KNOWN_SKILLS

router = APIRouter(
    prefix="/extract-skills",
    tags=["AI Extraction"],
)


# ── Schemas ───────────────────────────────────────────────────

class ExtractionRequest(BaseModel):
    """Input: raw resume or project description text."""
    text: str = Field(
        ...,
        min_length=10,
        description="Resume, project description, or any free-form text to extract skills from.",
        examples=["I built a CNN using PyTorch. I studied linear algebra and probability at university."],
    )


class ExtractionResponse(BaseModel):
    """Output: list of canonical skill names matching graph nodes."""
    skills:        list[str]
    total_found:   int
    available_skills_in_graph: list[str]  # Helpful for frontend dropdowns / validation


# ── Endpoint ──────────────────────────────────────────────────

@router.post(
    "/",
    response_model=ExtractionResponse,
    summary="Extract technical skills from resume text",
)
def extract_skills(request: ExtractionRequest):
    """
    Accepts free-form text and returns a list of technical skills
    found within it, normalized to match knowledge graph node names.

    Uses an LLM when `OPENAI_API_KEY` is set in the environment.
    Falls back to keyword matching otherwise (good for demos).

    ### Example Request
    ```json
    {
      "text": "I built image classifiers using PyTorch and studied
               linear algebra and probability at university. I use
               Git for version control and know SQL databases."
    }
    ```

    ### Example Response
    ```json
    {
      "skills": ["PyTorch", "Linear Algebra", "Probability", "Git", "Databases"],
      "total_found": 5,
      "available_skills_in_graph": ["Python", "PyTorch", ...]
    }
    ```
    """
    try:
        extracted = extract_skills_from_text(request.text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Skill extraction failed: {str(e)}",
        )

    return ExtractionResponse(
        skills=extracted,
        total_found=len(extracted),
        available_skills_in_graph=sorted(KNOWN_SKILLS),
    )
