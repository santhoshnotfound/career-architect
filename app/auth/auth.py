# app/auth/auth.py
# ============================================================
# JWT token creation and verification using python-jose.
#
# Why this file exists:
#   Centralises all JWT logic so the algorithm, expiry, and
#   signing key are configured in exactly one place. Routes and
#   dependencies import create_access_token / decode_access_token
#   without needing to know the underlying crypto details.
#
# Algorithm: HS256 (symmetric HMAC-SHA256).
#   One secret key is used to both sign (on login) and verify
#   (on every authenticated request). Suitable for a single-service
#   backend. For multi-service architectures, switch to RS256.
#
# Token payload:
#   sub  — the user's email address (string)
#   exp  — expiry timestamp (UTC, timezone-aware)
# ============================================================

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from app.auth.security import SECRET_KEY

ALGORITHM = "HS256"

# Default expiry read from environment, falls back to 24 hours.
# Operators can shorten this (e.g. "1") for higher-security deployments
# or lengthen it (e.g. "168") for convenience on internal tools.
ACCESS_TOKEN_EXPIRE_HOURS: int = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_HOURS", "24")
)


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed HS256 JWT.

    Args:
        subject:       The value to embed in the 'sub' claim.
                       We use the user's email address.
        expires_delta: Optional custom expiry duration.
                       Defaults to ACCESS_TOKEN_EXPIRE_HOURS.

    Returns:
        A compact JWT string, ready to send as a Bearer token.

    Usage:
        token = create_access_token(subject=user.email)
        # → "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...."
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """
    Decode and verify a JWT. Returns the 'sub' claim (email) on success.

    Returns None instead of raising on failure so callers can choose
    the appropriate response:
      - get_current_user          → turns None into HTTP 401
      - get_optional_current_user → returns None to the route (no error)

    Failure cases handled silently:
      - Expired token
      - Invalid signature (wrong secret key)
      - Malformed token string
      - Missing 'sub' claim
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub: Optional[str] = payload.get("sub")
        return sub  # None if 'sub' key is absent
    except JWTError:
        return None
