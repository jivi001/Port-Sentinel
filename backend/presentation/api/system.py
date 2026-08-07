"""
Presentation API — System routes (health, info, metrics).

Thin controllers that delegate to CQRS query handlers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.application.queries.dashboard import (
    DashboardQueryHandler,
    SystemHealthQuery,
    SystemInfoQuery,
    SystemMetricsQuery,
)
from backend.presentation.dependencies.injection import (
    get_dashboard_query_handler,
)

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def get_health(
    handler: DashboardQueryHandler = Depends(get_dashboard_query_handler),
) -> dict:
    """Lightweight health check."""
    return handler.handle_health(SystemHealthQuery())


@router.get("/info")
async def get_info(
    handler: DashboardQueryHandler = Depends(get_dashboard_query_handler),
) -> dict:
    """Detailed system information."""
    return handler.handle_info(SystemInfoQuery())


@router.get("/system/metrics")
async def get_system_metrics(
    handler: DashboardQueryHandler = Depends(get_dashboard_query_handler),
) -> dict:
    """Real-time system resource metrics for dashboard KPIs."""
    return handler.handle_metrics(SystemMetricsQuery())
