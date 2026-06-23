"""
Vigilant API — Threat Intelligence & Geolocation Routes.

Endpoints:
  GET /api/threats/geo      — Active threats with latitude/longitude
  GET /api/threats/countries— Threat counts summarized by country
  GET /api/threats/timeline — Historical threat timeline for replay
"""

import time
from collections import Counter
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import require_auth
from backend.core.state import get_traffic_accumulator
from backend.core.threat_intel import threat_manager

router = APIRouter(prefix="/api/threats", tags=["Threat Intelligence"])

# Simulated/Demonstration threats when running in local offline dev environment
SIMULATED_THREATS = [
    {"ip": "185.220.101.5", "city": "Berlin", "country": "DE", "latitude": 52.5200, "longitude": 13.4050, "risk": 8, "org": "Tor Exit Node IP", "port": 443},
    {"ip": "45.147.230.12", "city": "Moscow", "country": "RU", "latitude": 55.7558, "longitude": 37.6173, "risk": 9, "org": "Mirai Botnet Scanner", "port": 23},
    {"ip": "210.22.115.44", "city": "Shanghai", "country": "CN", "latitude": 31.2304, "longitude": 121.4737, "risk": 7, "org": "SSH Brute-Forcer", "port": 22},
    {"ip": "103.20.122.9", "city": "Seoul", "country": "KR", "latitude": 37.5665, "longitude": 126.9780, "risk": 6, "org": "Web Vulnerability Scanner", "port": 8080},
    {"ip": "198.51.100.72", "city": "New York", "country": "US", "latitude": 40.7128, "longitude": -74.0060, "risk": 5, "org": "Unusual outbound sync", "port": 443},
    {"ip": "101.36.120.10", "city": "Tokyo", "country": "JP", "latitude": 35.6762, "longitude": 139.6503, "risk": 8, "org": "Malicious Command Center", "port": 9001},
]


@router.get("/geo")
async def get_threat_geo(
    min_risk: int = Query(0, ge=0, le=10),
    _auth=Depends(require_auth)
):
    """
    Get geo-referenced active threat data.
    Falls back to high-fidelity simulated feeds if no active external connections exist.
    """
    accumulator = get_traffic_accumulator()
    if not accumulator:
        return [t for t in SIMULATED_THREATS if t["risk"] >= min_risk]

    now = time.time()
    active_ports = accumulator.get_port_table(now)
    
    threats = []
    seen_ips = set()
    
    for p in active_ports:
        ip = p.get("remote_ip", "0.0.0.0")
        if ip != "0.0.0.0" and ip not in seen_ips:
            meta = threat_manager.get_ip_metadata(ip)
            risk = max(p.get("risk_score", 0), meta.get("risk", 0))
            if risk >= min_risk:
                seen_ips.add(ip)
                threats.append({
                    "ip": ip,
                    "city": meta.get("city", "Unknown"),
                    "country": meta.get("country", "??"),
                    "latitude": meta.get("latitude", 0.0),
                    "longitude": meta.get("longitude", 0.0),
                    "risk": risk,
                    "org": meta.get("org", "Unknown"),
                    "port": p.get("port", 0)
                })

    # Return simulated fallback if empty (so globe displays data out-of-the-box)
    if not threats:
        return [t for t in SIMULATED_THREATS if t["risk"] >= min_risk]
        
    return threats


@router.get("/countries")
async def get_threat_countries(_auth=Depends(require_auth)):
    """
    Get active threat counts grouped by country.
    """
    geo_data = await get_threat_geo(min_risk=0, _auth=_auth)
    country_counts = Counter()
    for t in geo_data:
        country_counts[t["country"]] += 1
        
    return [
        {"country": country, "count": count}
        for country, count in country_counts.items()
    ]


@router.get("/timeline")
async def get_threat_timeline(
    hours: int = Query(24, ge=1, le=24),
    _auth=Depends(require_auth)
):
    """
    Get threat events grouped in time buckets for replay/scrubbing visualization.
    """
    accumulator = get_traffic_accumulator()
    if not accumulator:
        # Generate mock timeline for standalone dev mode
        now = time.time()
        timeline = []
        for i in range(12):
            t_val = now - (i * 300)
            timeline.append({
                "timestamp": t_val,
                "threats": [
                    {**t, "kb_s_in": 14.2 * (i % 3 + 1), "kb_s_out": 5.1 * (i % 2 + 1)}
                    for t in SIMULATED_THREATS[:(i % len(SIMULATED_THREATS) + 1)]
                ]
            })
        return timeline

    cutoff = time.time() - (hours * 3600)
    bucket_size = 300  # 5-minute intervals
    buckets: Dict[int, List[Dict[str, Any]]] = {}
    
    for port, dq in accumulator.cache._cache.items():
        for s in dq:
            if s.timestamp >= cutoff and s.remote_ip != "0.0.0.0":
                bucket_id = int(s.timestamp / bucket_size) * bucket_size
                if bucket_id not in buckets:
                    buckets[bucket_id] = []
                    
                meta = threat_manager.get_ip_metadata(s.remote_ip)
                buckets[bucket_id].append({
                    "ip": s.remote_ip,
                    "city": meta.get("city", "Unknown"),
                    "country": meta.get("country", "??"),
                    "latitude": meta.get("latitude", 0.0),
                    "longitude": meta.get("longitude", 0.0),
                    "risk": max(s.risk_score, meta.get("risk", 0)),
                    "org": s.org,
                    "port": s.port,
                    "kb_s_in": s.kb_s_in,
                    "kb_s_out": s.kb_s_out
                })
                
    response = []
    for bucket_ts, items in sorted(buckets.items()):
        response.append({
            "timestamp": bucket_ts,
            "threats": items
        })
        
    if not response:
        # Fallback mock timeline
        now = time.time()
        for i in range(12):
            t_val = now - (i * 300)
            response.append({
                "timestamp": t_val,
                "threats": [
                    {**t, "kb_s_in": 12.0, "kb_s_out": 6.5}
                    for t in SIMULATED_THREATS[:(i % len(SIMULATED_THREATS) + 1)]
                ]
            })
            
    return response
