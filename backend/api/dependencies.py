"""
Vigilant API Dependencies — Shared FastAPI dependency injection.

Provides authentication, authorization, and database session dependencies
used across all API route modules.
"""

from sqlalchemy.orm import Session
def get_db_session():
    """Yield a SQLAlchemy session from the global database instance."""
    from backend.core.db import get_database
    db = get_database()
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()
