"""
T2 — Integration Tests: Firewall command generation

Verifies netsh/pfctl command strings are correctly constructed
and that system-PID protection is enforced at the command layer.

All commands are MOCKED — no actual firewall rules are created.
"""

import sys
import platform
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, ".")

from backend.core.exceptions import SystemProcessProtectionError


# ===================================================================
# Windows — netsh advfirewall
# ===================================================================

class TestNetshCommandGeneration:
    """Windows: netsh advfirewall commands."""

    def test_block_creates_two_rules(self):
        """block_port should create both inbound and outbound rules."""
        from backend.os_adapters import win32_bridge

        with patch.object(win32_bridge, "is_windows", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            win32_bridge.block_port(port=8080, protocol="TCP")

        assert mock_run.call_count == 2  # in + out
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("dir=out" in c for c in calls)
        assert any("dir=in" in c for c in calls)

    def test_block_rule_names_contain_port(self):
        """Rule names should include the port number for identification."""
        from backend.os_adapters import win32_bridge

        with patch.object(win32_bridge, "is_windows", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            win32_bridge.block_port(port=9090, protocol="TCP")

        calls = str(mock_run.call_args_list)
        assert "9090" in calls
        assert "Sentinel_" in calls

    def test_unblock_deletes_both_rules(self):
        """unblock_port should delete both inbound and outbound rules."""
        from backend.os_adapters import win32_bridge

        with patch.object(win32_bridge, "is_windows", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            win32_bridge.unblock_port(port=8080)

        assert mock_run.call_count == 2  # delete In + Out
        calls = str(mock_run.call_args_list)
        assert "delete" in calls

    def test_unblock_is_idempotent_when_rules_already_absent(self):
        """Missing rules should be treated as already-unblocked success."""
        from backend.os_adapters import win32_bridge

        with patch.object(win32_bridge, "is_windows", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="No rules match the specified criteria.",
                stderr="",
            )
            assert win32_bridge.unblock_port(port=8080) is True

    def test_system_pid_protection_kill(self):
        """Attempt to kill system PID 4 should raise SystemProcessProtectionError."""
        from backend.os_adapters import win32_bridge

        with pytest.raises(SystemProcessProtectionError):
            win32_bridge.kill_process(pid=4)

    def test_system_pid_protection_suspend(self):
        """Attempt to suspend PID 0 should raise SystemProcessProtectionError."""
        from backend.os_adapters import win32_bridge

        with pytest.raises(SystemProcessProtectionError):
            win32_bridge.suspend_process(pid=0)

    def test_system_pid_protection_resume(self):
        """Attempt to resume PID 4 should raise SystemProcessProtectionError."""
        from backend.os_adapters import win32_bridge

        with pytest.raises(SystemProcessProtectionError):
            win32_bridge.resume_process(pid=4)


# ===================================================================
# macOS — pfctl
# ===================================================================

class TestPfctlCommandGeneration:
    """macOS: pfctl commands."""

    def test_system_pid_protection_launchd(self):
        """macOS launchd (PID 1) should be protected from kill."""
        from backend.os_adapters import darwin_bridge

        with pytest.raises(SystemProcessProtectionError):
            darwin_bridge.kill_process(pid=1)

    def test_system_pid_protection_kernel_task(self):
        """macOS kernel_task (PID 0) should be protected from suspend."""
        from backend.os_adapters import darwin_bridge

        with pytest.raises(SystemProcessProtectionError):
            darwin_bridge.suspend_process(pid=0)

    def test_pf_rule_tracking(self):
        """block_port should add the port to _active_rules."""
        from backend.os_adapters import darwin_bridge

        # Save original rules
        original_rules = darwin_bridge._active_rules.copy()
        try:
            with patch.object(darwin_bridge, "is_darwin", return_value=True), \
                 patch("subprocess.run") as mock_run, \
                 patch("builtins.open", MagicMock()):
                mock_run.return_value = MagicMock(returncode=0, stderr="pf enabled")
                darwin_bridge.block_port(port=7777, protocol="tcp")

            assert 7777 in darwin_bridge._active_rules
            assert "7777" in darwin_bridge._active_rules[7777]
        finally:
            # Restore
            darwin_bridge._active_rules.clear()
            darwin_bridge._active_rules.update(original_rules)

    def test_unblock_removes_from_tracking(self):
        """unblock_port should remove the port from _active_rules."""
        from backend.os_adapters import darwin_bridge

        original_rules = darwin_bridge._active_rules.copy()
        try:
            darwin_bridge._active_rules[8888] = "block drop on en0 proto tcp from any to any port 8888"

            with patch.object(darwin_bridge, "_reload_pf"), \
                 patch("builtins.open", MagicMock()):
                darwin_bridge.unblock_port(port=8888)

            assert 8888 not in darwin_bridge._active_rules
        finally:
            darwin_bridge._active_rules.clear()
            darwin_bridge._active_rules.update(original_rules)


# ===================================================================
# Cleanup — Both platforms
# ===================================================================

class TestFirewallCleanup:
    """Verify cleanup removes all rules."""

    def test_win32_cleanup_removes_sentinel_rules(self):
        """cleanup_all_rules should search for and delete all Sentinel_ rules."""
        from backend.os_adapters import win32_bridge

        show_output = (
            "Rule Name:                            Sentinel_Block_Out_8080\n"
            "Rule Name:                            Sentinel_Block_In_8080\n"
            "Rule Name:                            SomeOtherRule\n"
        )

        with patch.object(win32_bridge, "is_windows", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=show_output, stderr="")
            removed = win32_bridge.cleanup_all_rules()

        # Should delete 2 Sentinel_ rules, skip SomeOtherRule
        assert removed == 2

    def test_darwin_cleanup_clears_active_rules(self):
        """cleanup_all_rules should clear _active_rules dict."""
        from backend.os_adapters import darwin_bridge

        original_rules = darwin_bridge._active_rules.copy()
        try:
            darwin_bridge._active_rules[80] = "block drop..."
            darwin_bridge._active_rules[443] = "block drop..."

            with patch("subprocess.run"), \
                 patch("os.path.exists", return_value=True), \
                 patch("os.remove"):
                removed = darwin_bridge.cleanup_all_rules()

            assert removed == 2
            assert len(darwin_bridge._active_rules) == 0
        finally:
            darwin_bridge._active_rules.clear()
            darwin_bridge._active_rules.update(original_rules)
