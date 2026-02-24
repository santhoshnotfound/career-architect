# routes/health.py
# ------------------------------------------------------------
# Health check endpoint.
# Used by monitoring tools, load balancers, and during
# development to confirm the server is running correctly.
# This route has no database dependency by design — it should
# return OK even if the DB is temporarily unavailable.
# ------------------------------------------------------------

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check")
def health_check():
    """
    Returns a simple status response.

    Use this to verify:
      - The server is running
      - The API is reachable
      - Basic routing is working
    """
    return {"status": "ok"}
