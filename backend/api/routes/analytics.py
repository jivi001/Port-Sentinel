"""
Vigilant API — Analytics, Forensics & Threat Routes.

Endpoints:
  GET /api/analytics/top-talkers  — Top bandwidth consumers
  GET /api/audit/logs             — Security event audit trail
  GET /api/threats/geo            — Geo-aggregated threat data for globe
  GET /api/threats/countries       — Country-level statistics
"""

import time
import logging

from fastapi import APIRouter, Depends, Query

from backend.core.db import get_database

logger = logging.getLogger("vigilant.api.analytics")

router = APIRouter(tags=["Analytics & Forensics"])


@router.get("/api/analytics/top-talkers")
async def get_top_talkers(
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(10, ge=1, le=1000),
):
    """Identify applications with the highest traffic volume."""
    db = get_database()
    return db.get_top_talkers(hours=hours, limit=limit)


@router.get("/api/audit/logs")
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
):
    """Fetch recent security and policy events."""
    db = get_database()
    return db.get_audit_logs(limit=limit)


@router.get("/api/audit/logs/export")
async def export_audit_logs(
    format: str = Query("json", regex="^(json|csv)$"),
    hours: int = Query(24, ge=1, le=8760),
):
    """Export audit logs in JSON or CSV format."""
    db = get_database()
    logs = db.get_audit_logs(limit=10000)

    if format == "csv":
        import csv
        import io
        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        if logs:
            writer = csv.DictWriter(output, fieldnames=logs[0].keys())
            writer.writeheader()
            writer.writerows(logs)

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
        )

    return logs


@router.get("/api/threats/geo")
async def get_threat_geo_data():
    """
    Aggregated threat data with coordinates for Globe visualization.

    Returns connections with geolocation data for mapping threat
    origins and destinations on a 3D globe.
    """
    from backend.core.state import get_traffic_accumulator
    accumulator = get_traffic_accumulator()
    port_table = accumulator.get_port_table()

    geo_entries = []
    seen_ips = set()
    for entry in port_table:
        ip = entry.get("remote_ip", "0.0.0.0")
        if ip in ("0.0.0.0", "127.0.0.1") or ip.startswith("192.168.") or ip.startswith("10."):
            continue
        if ip in seen_ips:
            continue
        seen_ips.add(ip)
        geo_entries.append({
            "ip": ip,
            "port": entry.get("port"),
            "app_name": entry.get("app_name"),
            "country": entry.get("country", "??"),
            "org": entry.get("org", "Unknown"),
            "risk_score": entry.get("risk_score", 0),
            "kb_s_in": entry.get("kb_s_in", 0),
            "kb_s_out": entry.get("kb_s_out", 0),
            "protocol": entry.get("protocol", "TCP"),
        })

    return geo_entries


@router.get("/api/threats/countries")
async def get_threat_countries():
    """Country-level threat statistics."""
    from backend.core.state import get_traffic_accumulator
    accumulator = get_traffic_accumulator()
    port_table = accumulator.get_port_table()

    country_stats: dict[str, dict] = {}
    for entry in port_table:
        country = entry.get("country", "??")
        if country in ("LOCAL", "??"):
            continue
        if country not in country_stats:
            country_stats[country] = {
                "country": country,
                "connections": 0,
                "total_risk": 0,
                "total_kb_s": 0,
            }
        stats = country_stats[country]
        stats["connections"] += 1
        stats["total_risk"] = max(stats["total_risk"], entry.get("risk_score", 0))
        stats["total_kb_s"] += entry.get("kb_s_in", 0) + entry.get("kb_s_out", 0)

    return sorted(country_stats.values(), key=lambda x: x["total_risk"], reverse=True)
