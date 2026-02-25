# app/auth/security.py
# ============================================================
# Password hashing utilities using the bcrypt library directly.
#
# Why this file exists:
#   Isolates all cryptographic password logic in one place.
#   No FastAPI imports — pure utility functions that can be
#   called from routes, tests, or CLI scripts without side effects.
#
# Why bcrypt directly instead of passlib?
#   passlib's bcrypt backend has a known incompatibility with
#   bcrypt >= 4.x (it reads bcrypt.__about__.__version__ which
#   was removed in bcrypt 4.0). Using bcrypt's native API is
#   simpler, has no wrapper overhead, and stays compatible with
#   all modern bcrypt versions.
#
# Also loads SECRET_KEY from the environment for use by auth.py.
# Centralising the key here avoids importing os.environ in
# multiple places and makes key rotation easier to manage.
# ============================================================

import os
import logging

import bcrypt

logger = logging.getLogger(__name__)

# ── Secret key ────────────────────────────────────────────────
# Read from the environment. A hardcoded dev fallback is provided
# so the app starts without any .env configuration during development,
# but a loud warning is emitted to remind operators to set a real key.
SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-in-prod")

if SECRET_KEY == "dev-insecure-secret-change-in-prod":
    logger.warning(
        "SECRET_KEY is not set — using insecure dev default. "
        "Set SECRET_KEY in your .env before any non-local deployment."
    )


def hash_password(plain: str) -> str:
    """
    Hash a plain-text password with bcrypt.

    Uses bcrypt.gensalt() to generate a random salt (work factor 12).
    The resulting hash string includes the algorithm, cost factor, salt,
    and digest — everything needed to verify the password later.

    Returns a UTF-8 decoded string safe to store in a database Text column.
    Never store or log the plain-text password anywhere.
    """
    hashed_bytes = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return hashed_bytes.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Check whether a plain-text password matches a stored bcrypt hash.

    Returns True if they match, False otherwise.
    bcrypt is intentionally slow (~100ms per check) to resist brute-force attacks.

    Both arguments are encoded to bytes before comparison — bcrypt.checkpw
    handles the comparison in constant time to prevent timing attacks.
    """
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        # Guard against malformed hash strings (e.g. empty string, wrong prefix).
        # Return False rather than raising, so the route can return a clean 401.
        return False
