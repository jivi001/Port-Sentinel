"""
Presentation API — Ports and analytics routes.

Covers active ports, traffic history, analytics, and threat intelligence.
Merges the original analytics.py and threats.py routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.application.queries.threats import (
    ThreatCountriesQuery,
    ThreatGeoQuery,
    ThreatQueryHandler,
    ThreatTimelineQuery,
)
from backend.presentation.dependencies.injection import (
    get_database,
    get_threat_query_handler,
    get_traffic_accumulator,
)

router = APIRouter(prefix="/api", tags=["ports", "analytics", "threats"])


# --- Port Data ---

@router.get("/ports")
async def get_ports(accumulator=Depends(get_traffic_accumulator)) -> list:
    """Get current active port table."""
    return accumulator.get_port_table()


@router.get("/ports/{port}/history")
async def get_port_history(
    port: int,
    hours: int = 24,
    db=Depends(get_database),
) -> list:
    """Get traffic history for a specific port."""
    return db.get_traffic_history(port, hours)


@router.get("/blocked")
async def get_blocked_ports(db=Depends(get_database)) -> list:
    """Get all currently blocked ports."""
    return db.get_blocked_ports()


# --- Analytics ---

@router.get("/analytics/top-talkers")
async def get_top_talkers(
    hours: int = 24,
    limit: int = 10,
    db=Depends(get_database),
) -> list:
    """Get top bandwidth consumers."""
    return db.get_top_talkers(hours, limit)


@router.get("/audit/logs")
async def get_audit_logs(
    limit: int = 100,
    db=Depends(get_database),
) -> list:
    """Get security audit logs."""
    return db.get_audit_logs(limit)


# --- Threat Intelligence (merged from threats.py) ---

@router.get("/threats/geo")
async def get_threat_geo(
    min_risk: int = 0,
    handler: ThreatQueryHandler = Depends(get_threat_query_handler),
) -> list:
    """Get geo-referenced active threat data."""
    return handler.handle_geo(ThreatGeoQuery(min_risk=min_risk))


@router.get("/threats/countries")
async def get_threat_countries(
    handler: ThreatQueryHandler = Depends(get_threat_query_handler),
) -> list:
    """Get threat counts grouped by country."""
    return handler.handle_countries(ThreatCountriesQuery())


@router.get("/threats/timeline")
async def get_threat_timeline(
    hours: int = 24,
    handler: ThreatQueryHandler = Depends(get_threat_query_handler),
) -> list:
    """Get threat events in time buckets for replay visualization."""
    return handler.handle_timeline(ThreatTimelineQuery(hours=hours))


# --- Preferences ---

@router.get("/auth/preferences")
async def get_preferences(db=Depends(get_database)) -> dict:
    """Get user preferences."""
    return db.get_user_preferences()


@router.post("/auth/preferences")
async def set_preferences(
    prefs: dict,
    db=Depends(get_database),
) -> dict:
    """Set user preferences."""
    for key, value in prefs.items():
        db.set_user_preference(str(key), str(value))
    return {"success": True}
