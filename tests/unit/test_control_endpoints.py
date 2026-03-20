"""
T1 — Unit Tests: control endpoint error semantics

Verifies suspend/resume/kill endpoints return meaningful HTTP errors when
adapter-level operations fail.
"""

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

sys.path.insert(0, ".")

from backend import main


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint_name", "denied_prefix"),
    [
        ("suspend_process_endpoint", "Suspend denied"),
        ("resume_process_endpoint", "Resume denied"),
        ("kill_process_endpoint", "Kill denied"),
    ],
)
async def test_control_endpoint_returns_403_when_pid_exists_but_denied(
    endpoint_name, denied_prefix
):
    """If adapter returns False and PID exists, endpoint should return 403."""
    fake_bridge = SimpleNamespace(
        suspend_process=lambda pid: False,
        resume_process=lambda pid: False,
        kill_process=lambda pid: False,
    )

    with patch.object(main, "os_bridge", fake_bridge), patch(
        "backend.main.psutil.pid_exists", return_value=True
    ):
        endpoint = getattr(main, endpoint_name)
        with pytest.raises(HTTPException) as exc:
            await endpoint(4321)

    assert exc.value.status_code == 403
    assert denied_prefix in str(exc.value.detail)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint_name",
    [
        "suspend_process_endpoint",
        "resume_process_endpoint",
        "kill_process_endpoint",
    ],
)
async def test_control_endpoint_returns_404_when_pid_is_missing(endpoint_name):
    """If adapter returns False and PID does not exist, endpoint should return 404."""
    fake_bridge = SimpleNamespace(
        suspend_process=lambda pid: False,
        resume_process=lambda pid: False,
        kill_process=lambda pid: False,
    )

    with patch.object(main, "os_bridge", fake_bridge), patch(
        "backend.main.psutil.pid_exists", return_value=False
    ):
        endpoint = getattr(main, endpoint_name)
        with pytest.raises(HTTPException) as exc:
            await endpoint(999999)

    assert exc.value.status_code == 404
    assert "not found" in str(exc.value.detail).lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint_name", "action"),
    [
        ("suspend_process_endpoint", "suspend"),
        ("resume_process_endpoint", "resume"),
        ("kill_process_endpoint", "kill"),
    ],
)
async def test_control_endpoint_returns_success_payload(endpoint_name, action):
    """If adapter returns True, endpoint should return success payload."""
    fake_bridge = SimpleNamespace(
        suspend_process=lambda pid: True,
        resume_process=lambda pid: True,
        kill_process=lambda pid: True,
    )

    with patch.object(main, "os_bridge", fake_bridge):
        endpoint = getattr(main, endpoint_name)
        payload = await endpoint(2468)

    assert payload["success"] is True
    assert payload["pid"] == 2468
    assert payload["action"] == action
