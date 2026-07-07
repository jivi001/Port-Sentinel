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


def get_current_user(request: Request):
    """Validate token using VIGILANT_JWT_SECRET as a static API key."""
    import os
    from fastapi import HTTPException
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = auth_header.split(" ")[1]
    secret = os.environ.get("VIGILANT_JWT_SECRET", "default_insecure_secret")
    
    if token != secret:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return {"user": "admin"}


def get_os_bridge():
    """Provide the OS bridge for firewall operations."""
    from backend.core.state import get_os_bridge as get_global_os_bridge
    return get_global_os_bridge()


def get_influx():
    """Provide the InfluxDB writer."""
    from backend.core.state import get_influx as get_global_influx
    return get_global_influx()


def get_traffic_accumulator():
    """Provide the TrafficAccumulator."""
    from backend.core.state import get_traffic_accumulator as get_global_ta
    return get_global_ta()


def get_policy_engine():
    """Provide the PolicyEngine."""
    from backend.core.state import get_policy_engine as get_global_pe
    return get_global_pe()


def get_sniffer_process():
    """Provide the SnifferProcess."""
    from backend.core.state import get_sniffer_process as get_global_sp
    return get_global_sp()
