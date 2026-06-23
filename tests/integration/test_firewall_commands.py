"""
T2 — Integration Tests: Firewall command generation

Verifies netsh/pfctl command strings are correctly constructed
via the WindowsBridge and DarwinBridge classes.

All commands are MOCKED — no actual firewall rules are created.
"""

import sys
import platform
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, ".")

from backend.os_adapters.win32_bridge import WindowsBridge
from backend.os_adapters.darwin_bridge import DarwinBridge


# ===================================================================
# Windows — netsh advfirewall
# ===================================================================

class TestNetshCommandGeneration:
    """Windows: netsh advfirewall commands."""

    def test_block_creates_two_rules(self):
        """block_port should create both inbound and outbound rules."""
        bridge = WindowsBridge()

        with patch.object(WindowsBridge, "is_compatible", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            bridge.block_port(port=8080, protocol="TCP")

        assert mock_run.call_count == 2  # in + out
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("dir=out" in c for c in calls)
        assert any("dir=in" in c for c in calls)

    def test_block_rule_names_contain_port(self):
        """Rule names should include the port number for identification."""
        bridge = WindowsBridge()

        with patch.object(WindowsBridge, "is_compatible", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            bridge.block_port(port=9090, protocol="TCP")

        calls = str(mock_run.call_args_list)
        assert "9090" in calls
        assert "Vigilant_" in calls

    def test_unblock_deletes_both_rules(self):
        """unblock_port should delete both inbound and outbound rules."""
        bridge = WindowsBridge()

        with patch.object(WindowsBridge, "is_compatible", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            bridge.unblock_port(port=8080)

        calls = str(mock_run.call_args_list)
        assert "delete" in calls

    def test_unblock_is_idempotent_when_rules_already_absent(self):
        """Missing rules should be treated as already-unblocked success."""
        bridge = WindowsBridge()

        with patch.object(WindowsBridge, "is_compatible", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="No rules match the specified criteria.",
                stderr="",
            )
            assert bridge.unblock_port(port=8080) is True


# ===================================================================
# macOS — pfctl
# ===================================================================

class TestPfctlCommandGeneration:
    """macOS: pfctl commands."""

    def test_pf_rule_tracking(self):
        """block_port should add the port to _active_rules."""
        bridge = DarwinBridge()
        from backend.os_adapters.darwin_bridge import _active_rules

        # Save original rules
        original_rules = _active_rules.copy()
        try:
            with patch.object(DarwinBridge, "is_compatible", return_value=True), \
                 patch("subprocess.run") as mock_run, \
                 patch("builtins.open", MagicMock()):
                mock_run.return_value = MagicMock(returncode=0, stderr="pf enabled")
                bridge.block_port(port=7777, protocol="tcp")

            assert 7777 in _active_rules
            assert "7777" in _active_rules[7777]
        finally:
            # Restore
            _active_rules.clear()
            _active_rules.update(original_rules)

    def test_unblock_removes_from_tracking(self):
        """unblock_port should remove the port from _active_rules."""
        bridge = DarwinBridge()
        from backend.os_adapters.darwin_bridge import _active_rules, _write_pf_rules

        original_rules = _active_rules.copy()
        try:
            _active_rules[8888] = "block drop on en0 proto tcp from any to any port 8888"

            with patch.object(DarwinBridge, "is_compatible", return_value=True), \
                 patch("backend.os_adapters.darwin_bridge._reload_pf"), \
                 patch("builtins.open", MagicMock()):
                bridge.unblock_port(port=8888)

            assert 8888 not in _active_rules
        finally:
            _active_rules.clear()
            _active_rules.update(original_rules)


# ===================================================================
# Cleanup — Both platforms
# ===================================================================

class TestFirewallCleanup:
    """Verify cleanup removes all rules."""

    def test_win32_cleanup_removes_sentinel_rules(self):
        """cleanup_all_rules should search for and delete all Vigilant/Sentinel rules."""
        bridge = WindowsBridge()

        show_output = (
            "Rule Name:                            Vigilant_Block_Out_8080\n"
            "Rule Name:                            Sentinel_Block_In_8080\n"
            "Rule Name:                            SomeOtherRule\n"
        )

        with patch.object(WindowsBridge, "is_compatible", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=show_output, stderr="")
            removed = bridge.cleanup_all_rules()

        # Should delete 2 rules, skip SomeOtherRule
        assert removed == 2

    def test_darwin_cleanup_clears_active_rules(self):
        """cleanup_all_rules should clear _active_rules dict."""
        bridge = DarwinBridge()
        from backend.os_adapters.darwin_bridge import _active_rules

        original_rules = _active_rules.copy()
        try:
            _active_rules[80] = "block drop..."
            _active_rules[443] = "block drop..."

            with patch.object(DarwinBridge, "is_compatible", return_value=True), \
                 patch("subprocess.run"), \
                 patch("os.path.exists", return_value=True), \
                 patch("os.remove"):
                removed = bridge.cleanup_all_rules()

            assert removed == 2
            assert len(_active_rules) == 0
        finally:
            _active_rules.clear()
            _active_rules.update(original_rules)
