"""
Presentation Dependencies — FastAPI dependency injection wiring.

Provides FastAPI `Depends()` callables that extract services from
the application container. Route handlers use these instead of
importing global state directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from backend.container import Container
    from backend.application.commands.approvals import ApprovalCommandHandler
    from backend.application.commands.firewall import FirewallCommandHandler
    from backend.application.queries.dashboard import DashboardQueryHandler
    from backend.application.queries.threats import ThreatQueryHandler


def get_container(request: Request) -> "Container":
    """Get the application container from the ASGI app state."""
    return request.app.state.container


def get_database(request: Request):
    """Get the database repository."""
    return request.app.state.container.database


def get_event_bus(request: Request):
    """Get the event bus."""
    return request.app.state.container.event_bus


def get_traffic_accumulator(request: Request):
    """Get the traffic accumulator service."""
    return request.app.state.container.traffic_accumulator


def get_os_bridge(request: Request):
    """Get the OS bridge adapter."""
    return request.app.state.container.os_bridge


def get_policy_engine(request: Request):
    """Get the policy engine."""
    return request.app.state.container.policy_engine


def get_threat_service(request: Request):
    """Get the threat intelligence service."""
    return request.app.state.container.threat_service


def get_firewall_handler(request: Request) -> "FirewallCommandHandler":
    """Get a firewall command handler wired to the container."""
    from backend.application.commands.firewall import FirewallCommandHandler
    return FirewallCommandHandler(request.app.state.container)


def get_approval_handler(request: Request) -> "ApprovalCommandHandler":
    """Get an approval command handler wired to the container."""
    from backend.application.commands.approvals import ApprovalCommandHandler
    return ApprovalCommandHandler(request.app.state.container)


def get_dashboard_query_handler(request: Request) -> "DashboardQueryHandler":
    """Get a dashboard query handler wired to the container."""
    from backend.application.queries.dashboard import DashboardQueryHandler
    return DashboardQueryHandler(request.app.state.container)


def get_threat_query_handler(request: Request) -> "ThreatQueryHandler":
    """Get a threat query handler wired to the container."""
    from backend.application.queries.threats import ThreatQueryHandler
    return ThreatQueryHandler(request.app.state.container)
