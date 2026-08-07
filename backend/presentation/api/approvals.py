"""
Presentation API — Approval workflow routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.application.commands.approvals import (
    ApprovalCommandHandler,
    RequestApprovalCommand,
    ResolveApprovalCommand,
)
from backend.presentation.dependencies.injection import (
    get_approval_handler,
    get_database,
)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class ResolveRequest(BaseModel):
    status: str  # "approved" | "rejected"


@router.post("/request")
async def request_approval(
    pid: int,
    reason: str = "Manual request",
    app_name: str | None = None,
    handler: ApprovalCommandHandler = Depends(get_approval_handler),
) -> dict:
    """Request analyst approval for a process action."""
    if pid <= 0:
        raise HTTPException(status_code=400, detail="Invalid PID")
    return handler.handle_request(
        RequestApprovalCommand(pid=pid, app_name=app_name, reason=reason)
    )


@router.get("")
async def get_approvals(db=Depends(get_database)) -> list:
    """Get all approval requests."""
    return db.get_pending_approvals()


@router.post("/{approval_id}/resolve")
async def resolve_approval(
    approval_id: int,
    body: ResolveRequest,
    handler: ApprovalCommandHandler = Depends(get_approval_handler),
) -> dict:
    """Resolve a pending approval."""
    if body.status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=400, detail="Status must be 'approved' or 'rejected'"
        )
    return handler.handle_resolve(
        ResolveApprovalCommand(
            approval_id=approval_id, status=body.status
        )
    )
