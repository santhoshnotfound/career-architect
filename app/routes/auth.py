# app/routes/auth.py
# ============================================================
# Authentication endpoints: user registration and login.
#
# Why this file exists:
#   Provides the two endpoints that bootstrap the auth lifecycle.
#   All crypto logic lives in app/auth/ — this file is a thin
#   HTTP layer that calls those utilities and returns tokens.
#
# Endpoints:
#   POST /auth/register — create a new account, returns JWT
#   POST /auth/login    — verify credentials, returns JWT
#
# No OAuth. No third-party providers. Email + password only.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas
from app.auth.security import hash_password, verify_password
from app.auth.auth import create_access_token

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)

# A valid bcrypt hash used as a timing dummy when the email does not exist.
# This ensures verify_password() always runs (constant-time ~100ms),
# preventing an attacker from enumerating valid emails by measuring
# the difference in response time between "user not found" (fast) and
# "wrong password" (slow, bcrypt). The actual hash value is irrelevant
# — it will never match a real password.
_DUMMY_HASH = "$2b$12$eImiTXuWVxfM37uY4JANjQ.ZfvqJBEWLMVMSHAkEZ1MjfT89pR3ey"


@router.post(
    "/register",
    response_model=schemas.TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(body: schemas.UserRegister, db: Session = Depends(get_db)):
    """
    Create a new user account and return a JWT immediately.

    The password is hashed with bcrypt before being stored.
    The plain-text password is never logged or persisted.

    Returns a bearer token on success so the user is automatically
    logged in after registration — no separate login call needed.

    ### Errors
    - **409 Conflict** — email is already registered
    - **422 Unprocessable Entity** — invalid email format or password too short

    ### Example
    ```json
    { "email": "alice@example.com", "password": "s3curepass" }
    ```
    """
    try:
        user = crud.create_user(
            db=db,
            email=body.email,
            hashed_password=hash_password(body.password),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    token = create_access_token(subject=user.email)
    return schemas.TokenResponse(access_token=token)


@router.post(
    "/login",
    response_model=schemas.TokenResponse,
    summary="Log in and receive a JWT",
)
def login(body: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate with email and password, receive a bearer token.

    The same error message is returned for "email not found" and
    "wrong password" to prevent user enumeration attacks.
    bcrypt always runs (via dummy hash) to prevent timing attacks.

    ### Errors
    - **401 Unauthorized** — email not registered or password is wrong

    ### Example
    ```json
    { "email": "alice@example.com", "password": "s3curepass" }
    ```

    ### Using the token
    Include it in subsequent requests:
    ```
    Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    ```
    """
    user = crud.get_user_by_email(db=db, email=body.email)

    # Always call verify_password regardless of whether the user was found.
    # If user is None, verify against a dummy hash so the response time
    # is identical to the "wrong password" case (~100ms bcrypt round trip).
    password_ok = verify_password(
        body.password,
        user.hashed_password if user else _DUMMY_HASH,
    )

    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(subject=user.email)
    return schemas.TokenResponse(access_token=token)
