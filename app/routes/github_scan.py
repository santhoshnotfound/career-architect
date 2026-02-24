# app/routes/github_scan.py
# ============================================================
# HTTP endpoint for GitHub profile scanning.
# All scanning logic lives in app/ai/github_scanner.py.
# This file only handles HTTP parsing, validation, and errors.
# ============================================================

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.ai.github_scanner import scan_github_profile
from app.ai.skill_extractor import KNOWN_SKILLS

router = APIRouter(prefix="/scan-github", tags=["GitHub Scanner"])


class GithubScanRequest(BaseModel):
    """Input: any GitHub URL or username format."""
    github_input: str = Field(
        ...,
        min_length=1,
        description=(
            "GitHub username or profile URL. Accepts any format: "
            "'santhosh', 'github.com/santhosh', 'https://github.com/santhosh'"
        ),
        examples=["github.com/santhosh", "torvalds"],
    )


class SignalDetail(BaseModel):
    """A single skill detection signal — what triggered the skill detection."""
    skill:  str   # Canonical skill name
    source: str   # e.g. "repo/my-project/requirements.txt"
    detail: str   # e.g. "Package: torch==2.0.0"


class GithubScanResponse(BaseModel):
    """Output: detected skills with full transparency on what was found."""
    username:      str | None
    skills:        list[str]
    total_found:   int
    repos_scanned: int
    signals:       list[SignalDetail]
    available_skills_in_graph: list[str]
    error:         str | None


@router.post(
    "/",
    response_model=GithubScanResponse,
    summary="Scan a GitHub profile and extract technical skills",
)
def scan_github(request: GithubScanRequest):
    """
    Scans a public GitHub profile and automatically detects technical skills
    from repositories, dependencies, file structures, and topic tags.

    No GitHub token required for public profiles (60 requests/hour free).
    Set the `GITHUB_TOKEN` environment variable to increase to 5000/hour.

    ### What is scanned
    - Repository primary programming languages
    - Repository topic tags (e.g. `#pytorch`, `#machine-learning`)
    - `requirements.txt` — Python package dependencies
    - `package.json` — Node.js dependencies
    - File tree — Dockerfiles, notebooks, SQL files, shell scripts
    - Repository names and descriptions

    ### Example Request
    ```json
    { "github_input": "github.com/yourusername" }
    ```

    ### Example Response
    ```json
    {
      "username": "yourusername",
      "skills": ["Python", "PyTorch", "Machine Learning", "Git"],
      "repos_scanned": 12,
      "signals": [
        {
          "skill": "PyTorch",
          "source": "repo/cnn-classifier/requirements.txt",
          "detail": "Package: torch==2.0.0"
        }
      ]
    }
    ```
    """
    result = scan_github_profile(request.github_input)

    # If the scanner returned an error, surface it as HTTP 422
    if result["error"] and not result["skills"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result["error"],
        )

    return GithubScanResponse(
        username      = result["username"],
        skills        = result["skills"],
        total_found   = len(result["skills"]),
        repos_scanned = result["repos_scanned"],
        signals       = [SignalDetail(**s) for s in result["signals"]],
        available_skills_in_graph = sorted(KNOWN_SKILLS),
        error         = result["error"],
    )
