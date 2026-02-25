# app/auth/dependencies.py
# ============================================================
# FastAPI dependency functions for JWT authentication.
#
# Why this file exists:
#   FastAPI dependencies are reusable "building blocks" injected
#   into route functions via Depends(). Putting them here keeps
#   route files clean and makes auth logic easy to test in isolation.
#
# Two dependencies are provided:
#
#   get_current_user(token, db) → User
#     Use on routes that REQUIRE a logged-in user.
#     Raises HTTP 401 if the token is absent, expired, or invalid.
#
#   get_optional_current_user(token, db) → User | None
#     Use on routes that OPTIONALLY benefit from a logged-in user.
#     Returns None silently if no token is present or the token is bad.
#     Never raises an HTTP error — always safe to call.
#
# Usage in routes:
#   # Required:
#   def my_route(user: User = Depends(get_current_user)):
#
#   # Optional (e.g. POST /roadmap/ history logging):
#   def my_route(user: Optional[User] = Depends(get_optional_current_user)):
#
# Important note on session deduplication:
#   FastAPI deduplicates Depends() calls within a single request.
#   Even though get_db appears in both get_optional_current_user
#   and the route itself, the database session is created only once.
# ============================================================

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth.auth import decode_access_token

# ── OAuth2 scheme ─────────────────────────────────────────────
# OAuth2PasswordBearer extracts the token from the
#   Authorization: Bearer <token>
# header. tokenUrl is shown in /docs for the interactive auth UI.
#
# CRITICAL: auto_error=False
#   With the default auto_error=True, FastAPI raises HTTP 401
#   immediately if the Authorization header is absent — before
#   the route function even runs. Setting auto_error=False makes
#   the token value None instead, letting us handle both the
#   "required auth" and "optional auth" cases in one scheme.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency for routes that REQUIRE authentication.

    Flow:
      1. Extract Bearer token from Authorization header (auto_error=False
         means token is None if the header is absent).
      2. Decode and verify the JWT — get the email from 'sub'.
      3. Look up the user in the database by email.
      4. Return the User ORM object to the route.

    Raises:
      HTTP 401 with WWW-Authenticate: Bearer header on any failure:
        - No Authorization header
        - Token is expired, malformed, or has wrong signature
        - Email in token does not match any user in the DB

    Why look up the user from DB?
      Allows future account deactivation (add is_active flag) to take
      effect immediately without waiting for token expiry.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    email = decode_access_token(token)
    if email is None:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user


def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    FastAPI dependency for routes where authentication is OPTIONAL.

    Returns the User ORM object if a valid token is present.
    Returns None if:
      - No Authorization header is provided
      - The token is expired, malformed, or invalid
      - The email in the token no longer exists in the DB

    Never raises an HTTP exception — this is intentional.
    Used by POST /roadmap/ to conditionally save history when a
    user is logged in, without breaking anonymous access.
    """
    if token is None:
        return None

    email = decode_access_token(token)
    if email is None:
        return None

    return db.query(User).filter(User.email == email).first()
