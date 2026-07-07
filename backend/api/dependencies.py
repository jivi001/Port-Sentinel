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

def get_db_session():
    """Yield a SQLAlchemy session from the global database instance."""
    from backend.core.db import get_database
    db = get_database()
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()
