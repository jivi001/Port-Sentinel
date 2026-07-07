"""
Vigilant API — Analyst Approval Workflow Routes.

Provides detection → alerting → risk scoring → recommendation →
analyst approval workflow (replaces automatic process termination).

Endpoints:
  POST /api/approvals/request             — Request analyst approval
  GET  /api/approvals                     — List pending approvals
  POST /api/approvals/{id}/resolve        — Approve or reject
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
import asyncio
from pydantic import BaseModel

from backend.core.db import SQLiteDB, get_database
from backend.api.dependencies import get_current_user, get_db_session

logger = logging.getLogger("vigilant.api.approvals")

router = APIRouter(prefix="/api/approvals", tags=["Analyst Approvals"], dependencies=[Depends(get_current_user)])


class ApprovalResolveRequest(BaseModel):
    """Request body for resolving an approval."""
    status: str  # "approved" or "rejected"


@router.post("/request")
async def request_approval_endpoint(
    pid: int = Query(...),
    app_name: str = Query(None),
    reason: str = Query("Manual request"),
    db: SQLiteDB = Depends(get_database)
):
    """Submit a new analyst approval request for a detected threat action."""
    approval_id = await asyncio.to_thread(
        db.create_analyst_approval,
        action_type="suspend_process",
        target_identifier=str(pid),
        reason=reason,
    )
    await asyncio.to_thread(
        db.insert_audit_log,
        event_type="approval_requested",
        message=f"Approval requested for PID {pid}",
        severity="info",
        details=f"App: {app_name}, Reason: {reason}, Approval ID: {approval_id}",
    )
    return {
        "success": True,
        "pid": pid,
        "action": "request_approval",
        "approval_id": approval_id,
    }


@router.get("")
async def get_approvals(db: SQLiteDB = Depends(get_database)):
    """List all pending analyst approval requests, ordered by risk score."""
    return await asyncio.to_thread(db.get_pending_approvals)


@router.post("/{approval_id}/resolve")
async def resolve_approval(
    approval_id: int,
    payload: ApprovalResolveRequest,
    db: SQLiteDB = Depends(get_database)
):
    """Resolve a pending approval as approved or rejected."""
    if payload.status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="Status must be 'approved' or 'rejected'",
        )

    success = await asyncio.to_thread(
        db.update_approval_status,
        approval_id, payload.status, "system"
    )
    if not success:
        raise HTTPException(status_code=404, detail="Approval not found")

    severity = "info" if payload.status == "approved" else "warning"
    await asyncio.to_thread(
        db.insert_audit_log,
        event_type="approval_resolved",
        message=f"Approval {approval_id} {payload.status} by system",
        severity=severity,
        details=f"Approval ID: {approval_id}, Status: {payload.status}",
    )
    return {
        "success": True,
        "approval_id": approval_id,
        "status": payload.status,
    }
