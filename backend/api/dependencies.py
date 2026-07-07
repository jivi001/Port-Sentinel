"""
Vigilant API Dependencies — Shared FastAPI dependency injection.

Provides authentication, authorization, and database session dependencies
used across all API route modules.
"""

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.core.auth import decode_access_token
from backend.core.models import User, RoleEnum

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_token(request: Request, token_from_header: str = Depends(oauth2_scheme)) -> str:
    """Extract token from Cookie or fallback to Authorization header."""
    token = request.cookies.get("sentinel_session")
    if not token:
        token = token_from_header
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def get_db_session():
    """Yield a SQLAlchemy session from the global database instance."""
    from backend.core.db import get_database
    db = get_database()
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    token: str = Depends(get_token),
    session: Session = Depends(get_db_session),
) -> User:
    """Decode JWT and return the authenticated User record."""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
        
    jti = payload.get("jti")
    if jti:
        from backend.core.db import get_database
        db = get_database()
        if db.is_token_revoked(jti):
            raise HTTPException(
                status_code=401,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    user = session.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


def require_auth(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """Gate endpoints: require valid JWT. Stores user on request.state."""
    request.state.user = user
    return user


def require_role(allowed_roles: list):
    """Factory for role-based access control dependency."""
    def role_checker(user: User = Depends(get_current_user)):
        if user.role not in [r.value if hasattr(r, 'value') else r for r in allowed_roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker


require_admin = require_role([RoleEnum.ADMIN])
require_analyst = require_role([RoleEnum.ADMIN, RoleEnum.ANALYST])
