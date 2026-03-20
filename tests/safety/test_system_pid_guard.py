"""
T5 — Safety Tests: System PID Guard

Verifies that PIDs 0, 1, and 4 are protected from all dangerous
operations (kill, suspend, resume) on both Windows and macOS.

This is a CRITICAL safety boundary — no code change should ever
allow operations on these PIDs without explicit guard removal.
"""

import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, ".")

from backend.core.exceptions import SystemProcessProtectionError


# ===================================================================
# System PID definitions
# ===================================================================

# PID 0: Idle (Windows) / kernel_task (macOS)
# PID 1: launchd (macOS) — not in Windows protected set but tested anyway
# PID 4: System (Windows)

PROTECTED_WIN = {0, 4}
PROTECTED_MAC = {0, 1}
ALL_PROTECTED = PROTECTED_WIN | PROTECTED_MAC  # {0, 1, 4}


# ===================================================================
# Windows System PID Guard
# ===================================================================

class TestWindowsSystemPIDGuard:
    """Verify Windows system PIDs cannot be operated on."""

    @pytest.mark.parametrize("pid", sorted(PROTECTED_WIN))
    def test_kill_blocked(self, pid):
        """kill_process should raise for system PIDs."""
        from backend.os_adapters import win32_bridge
        with pytest.raises(SystemProcessProtectionError):
            win32_bridge.kill_process(pid)

    @pytest.mark.parametrize("pid", sorted(PROTECTED_WIN))
    def test_suspend_blocked(self, pid):
        """suspend_process should raise for system PIDs."""
        from backend.os_adapters import win32_bridge
        with pytest.raises(SystemProcessProtectionError):
            win32_bridge.suspend_process(pid)

    @pytest.mark.parametrize("pid", sorted(PROTECTED_WIN))
    def test_resume_blocked(self, pid):
        """resume_process should raise for system PIDs."""
        from backend.os_adapters import win32_bridge
        with pytest.raises(SystemProcessProtectionError):
            win32_bridge.resume_process(pid)


# ===================================================================
# macOS System PID Guard
# ===================================================================

class TestDarwinSystemPIDGuard:
    """Verify macOS system PIDs cannot be operated on."""

    @pytest.mark.parametrize("pid", sorted(PROTECTED_MAC))
    def test_kill_blocked(self, pid):
        """kill_process should raise for system PIDs."""
        from backend.os_adapters import darwin_bridge
        with pytest.raises(SystemProcessProtectionError):
            darwin_bridge.kill_process(pid)

    @pytest.mark.parametrize("pid", sorted(PROTECTED_MAC))
    def test_suspend_blocked(self, pid):
        """suspend_process should raise for system PIDs."""
        from backend.os_adapters import darwin_bridge
        with pytest.raises(SystemProcessProtectionError):
            darwin_bridge.suspend_process(pid)

    @pytest.mark.parametrize("pid", sorted(PROTECTED_MAC))
    def test_resume_blocked(self, pid):
        """resume_process should raise for system PIDs."""
        from backend.os_adapters import darwin_bridge
        with pytest.raises(SystemProcessProtectionError):
            darwin_bridge.resume_process(pid)


# ===================================================================
# Cross-platform verification
# ===================================================================

class TestCrossPlatformPIDGuard:
    """Verify PID protection constants are correct."""

    def test_windows_protected_set_includes_system(self):
        """Windows PROTECTED_PIDS should include PID 4 (System)."""
        from backend.os_adapters.win32_bridge import PROTECTED_PIDS_WIN
        assert 4 in PROTECTED_PIDS_WIN

    def test_windows_protected_set_includes_idle(self):
        """Windows PROTECTED_PIDS should include PID 0 (Idle)."""
        from backend.os_adapters.win32_bridge import PROTECTED_PIDS_WIN
        assert 0 in PROTECTED_PIDS_WIN

    def test_darwin_protected_set_includes_kernel_task(self):
        """macOS PROTECTED_PIDS should include PID 0 (kernel_task)."""
        from backend.os_adapters.darwin_bridge import PROTECTED_PIDS_MAC
        assert 0 in PROTECTED_PIDS_MAC

    def test_darwin_protected_set_includes_launchd(self):
        """macOS PROTECTED_PIDS should include PID 1 (launchd)."""
        from backend.os_adapters.darwin_bridge import PROTECTED_PIDS_MAC
        assert 1 in PROTECTED_PIDS_MAC

    def test_non_system_pid_not_protected(self):
        """A regular PID like 5678 should NOT be in any protected set."""
        from backend.os_adapters.win32_bridge import PROTECTED_PIDS_WIN
        from backend.os_adapters.darwin_bridge import PROTECTED_PIDS_MAC
        assert 5678 not in PROTECTED_PIDS_WIN
        assert 5678 not in PROTECTED_PIDS_MAC

    def test_exception_message_includes_pid(self):
        """SystemProcessProtectionError should include the PID in its message."""
        err = SystemProcessProtectionError(4, "kill")
        assert "4" in str(err)
        assert "kill" in str(err).lower()
