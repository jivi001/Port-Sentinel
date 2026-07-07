"""
Vigilant API — User Preferences Routes.

Endpoints:
  GET  /api/auth/preferences — Retrieve user preferences
  POST /api/auth/preferences — Update user preferences
"""

import logging
import asyncio
from fastapi import APIRouter, Depends, Body
from backend.api.dependencies import get_current_user
from backend.core.db import get_database

logger = logging.getLogger("vigilant.api.auth")

router = APIRouter(prefix="/api/auth", tags=["Authentication"], dependencies=[Depends(get_current_user)])


@router.get("/preferences")
async def get_preferences():
    """Retrieve all user preferences from the database."""
    db = get_database()
    return await asyncio.to_thread(db.get_user_preferences)


@router.post("/preferences")
async def set_preferences(payload: dict = Body(...)):
    """Save user preferences (key-value pairs) in the database."""
    db = get_database()
    for k, v in payload.items():
        await asyncio.to_thread(db.set_user_preference, k, str(v))
    return {"success": True}
