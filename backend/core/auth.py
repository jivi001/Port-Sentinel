"""
Vigilant Authentication — JWT tokens and password hashing.

Security:
  - JWT secret MUST be set via VIGILANT_JWT_SECRET environment variable
  - Falls back to auto-generated secret (persisted in config DB) if unset
  - bcrypt password hashing with automatic salt
"""

import os
import secrets
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

logger = logging.getLogger("vigilant.auth")

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def _resolve_jwt_secret() -> str:
    """Resolve the JWT signing secret from environment or generate one."""
    secret = (
        os.environ.get("VIGILANT_JWT_SECRET")
        or os.environ.get("SENTINEL_JWT_SECRET")
    )
    if secret and secret != "CHANGE_ME_BEFORE_DEPLOY":
        return secret

    # Fail fast if secret is not configured
    logger.critical(
        "CRITICAL ERROR: VIGILANT_JWT_SECRET is not configured! "
        "A secure secret must be provided to sign sessions. "
        "Generate one using: openssl rand -hex 32"
    )
    import sys
    sys.exit(1)


SECRET_KEY = _resolve_jwt_secret()
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4())
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a signed JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "refresh"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token. Returns None if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except InvalidTokenError:
        return None
