"""JWT authentication for Local Sidekick API."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from server.deps import get_firestore
from server.models.schemas import TokenResponse, UserLogin, UserRegister
from server.services.firestore_client import FirestoreClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    if os.environ.get("ENV", "development") == "production":
        raise RuntimeError("JWT_SECRET must be set in production")
    JWT_SECRET = "dev-secret-do-not-use-in-production"

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRATION_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


# ---------------------------------------------------------------------------
# Dependency: get current user from JWT
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency that extracts and validates the JWT bearer token."""
    payload = _verify_token(credentials.credentials)
    return {"user_id": payload["sub"], "email": payload.get("email", "")}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(body: UserRegister):
    """Register a new user with email and password."""
    db = get_firestore()

    # Check if user already exists
    existing_id, _ = await db.find_user_by_email(body.email)
    if existing_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    user_id = str(uuid.uuid4())
    hashed_pw = pwd_context.hash(body.password)

    await db.create_user(
        user_id,
        {
            "email": body.email,
            "password_hash": hashed_pw,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    token = _create_token(user_id, body.email)
    logger.info("User registered: %s", user_id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin):
    """Authenticate with email and password, returning a JWT."""
    db = get_firestore()

    user_id, user_doc = await db.find_user_by_email(body.email)
    if user_id is None or user_doc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not pwd_context.verify(body.password, user_doc.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = _create_token(user_id, body.email)
    logger.info("User logged in: %s", user_id)
    return TokenResponse(access_token=token)
