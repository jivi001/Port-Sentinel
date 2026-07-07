"""
Vigilant API — Authentication Routes.

Endpoints:
  POST /api/auth/login   — OAuth2 password grant → JWT
  GET  /api/auth/me       — Current user profile
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, constr

from backend.core.auth import verify_password, create_access_token, create_refresh_token, decode_access_token
from backend.core.models import User
from backend.api.dependencies import get_db_session, get_current_user, get_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login")
def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db_session),
):
    """Authenticate user and return JWT access token via HttpOnly Cookie."""
    from backend.core.db import get_database
    db = get_database()
    client_ip = request.client.host if request.client else "unknown"

    if db.is_ip_locked_out(client_ip):
        raise HTTPException(
            status_code=403,
            detail="Account temporarily locked due to multiple failed login attempts. Try again later."
        )

    user = session.execute(
        select(User).where(User.username == form_data.username)
    ).scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        db.record_failed_login(client_ip)
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    db.reset_failed_login(client_ip)
    
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username, "role": user.role}
    )
    
    import uuid
    csrf_token = str(uuid.uuid4())
    
    # 15 minutes max-age for access token
    response.set_cookie(
        key="sentinel_session",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=15 * 60,
    )
    # 7 days max-age for refresh token
    response.set_cookie(
        key="sentinel_refresh",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/api/auth/refresh",
        max_age=7 * 24 * 60 * 60,
    )
    # CSRF token cookie (not HttpOnly so frontend can read it)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    
    # Return tokens in body as well to support legacy CLI/API consumers
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "csrf_token": csrf_token
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    token: str = Depends(get_token)
):
    """Revoke current token and clear session cookies."""
    payload = decode_access_token(token)
    from backend.core.db import get_database
    db = get_database()
    
    if payload and "jti" in payload:
        db.revoke_token(
            jti=payload["jti"],
            expires_at=payload["exp"],
            reason="User logout",
            revoked_by=current_user.username
        )
        
    # Also revoke refresh token if it exists in cookies
    refresh_cookie = request.cookies.get("sentinel_refresh")
    if refresh_cookie:
        refresh_payload = decode_access_token(refresh_cookie)
        if refresh_payload and "jti" in refresh_payload:
            db.revoke_token(
                jti=refresh_payload["jti"],
                expires_at=refresh_payload["exp"],
                reason="User logout",
                revoked_by=current_user.username
            )
    
    response.delete_cookie("sentinel_session", path="/")
    response.delete_cookie("sentinel_refresh", path="/api/auth/refresh")
    response.delete_cookie("csrf_token", path="/")
    return {"success": True}

@router.post("/refresh")
def refresh_token(request: Request, response: Response):
    """Issue a new access token using a valid refresh token cookie."""
    refresh_cookie = request.cookies.get("sentinel_refresh")
    if not refresh_cookie:
        raise HTTPException(status_code=401, detail="Missing refresh token")
        
    payload = decode_access_token(refresh_cookie)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    jti = payload.get("jti")
    from backend.core.db import get_database
    db = get_database()
    if jti and db.is_token_revoked(jti):
        raise HTTPException(status_code=401, detail="Refresh token revoked")
        
    # Issue new access token
    new_access = create_access_token(
        data={"sub": payload.get("sub"), "role": payload.get("role")}
    )
    
    response.set_cookie(
        key="sentinel_session",
        value=new_access,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=15 * 60,
    )
    
    return {"access_token": new_access, "token_type": "bearer"}


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


class PreferencesSchema(BaseModel):
    # Allowed keys
    __root__: dict[constr(max_length=50), constr(max_length=200)]


@router.post("/preferences")
def set_preferences(
    prefs: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session)
):
    """Set preferences for the current logged-in user."""
    from backend.core.db import get_database
    db = get_database()
    
    allowed_keys = {"refresh_interval", "alert_threshold", "sentinel-theme"}
    
    for k, v in prefs.items():
        if k not in allowed_keys:
            continue
        db.set_user_preference(current_user.id, k, str(v)[:200])
    return {"success": True}
