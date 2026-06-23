"""
Vigilant API — Authentication Routes.

Endpoints:
  POST /api/auth/login   — OAuth2 password grant → JWT
  GET  /api/auth/me       — Current user profile
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.core.auth import verify_password, create_access_token
from backend.core.models import User
from backend.api.dependencies import get_db_session, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db_session),
):
    """Authenticate user and return JWT access token."""
    user = session.execute(
        select(User).where(User.username == form_data.username)
    ).scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
    }


@router.get("/preferences")
def get_preferences(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session)
):
    """Get preferences for the current logged-in user."""
    from backend.core.db import get_database
    db = get_database()
    return db.get_user_preferences(current_user.id)


@router.post("/preferences")
def set_preferences(
    prefs: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session)
):
    """Set preferences for the current logged-in user."""
    from backend.core.db import get_database
    db = get_database()
    for k, v in prefs.items():
        db.set_user_preference(current_user.id, k, str(v))
    return {"success": True}
