"""
T5 — Safety Tests: atexit firewall rule cleanup

Verifies that atexit hooks properly clean up all Vigilant/Sentinel firewall
rules on both Windows and macOS, preventing orphaned rules after crash.
"""

import sys
import os
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, ".")

from backend.os_adapters.win32_bridge import WindowsBridge
from backend.os_adapters.darwin_bridge import DarwinBridge
from backend.core.exceptions import CleanupError


class TestAtexitCleanupWindows:
    """Windows atexit cleanup."""

    def test_cleanup_called_removes_all_rules(self):
        """cleanup_all_rules should remove every Sentinel/Vigilant rule."""
        bridge = WindowsBridge()

        show_output = (
            "Rule Name:                            Vigilant_Block_Out_80\n"
            "Rule Name:                            Sentinel_Block_In_80\n"
            "Rule Name:                            Vigilant_Block_Out_443\n"
            "Rule Name:                            Sentinel_Block_In_443\n"
        )

        with patch.object(WindowsBridge, "is_compatible", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=show_output, stderr="")
            removed = bridge.cleanup_all_rules()

        assert removed == 4

    def test_cleanup_handles_no_rules(self):
        """cleanup_all_rules with no Vigilant/Sentinel rules should return 0."""
        bridge = WindowsBridge()

        show_output = "Rule Name:                            WindowsFirewall\n"

        with patch.object(WindowsBridge, "is_compatible", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=show_output, stderr="")
            removed = bridge.cleanup_all_rules()

        assert removed == 0

    def test_cleanup_survives_subprocess_error(self):
        """cleanup should not crash if subprocess fails (graceful degradation)."""
        bridge = WindowsBridge()

        with patch.object(WindowsBridge, "is_compatible", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("netsh crashed")

            with pytest.raises(CleanupError):
                bridge.cleanup_all_rules()


class TestAtexitCleanupDarwin:
    """macOS atexit cleanup."""

    def test_cleanup_clears_active_rules(self):
        """cleanup_all_rules should clear _active_rules and disable pf."""
        bridge = DarwinBridge()
        from backend.os_adapters.darwin_bridge import _active_rules

        original = _active_rules.copy()
        try:
            _active_rules[80] = "block rule"
            _active_rules[443] = "block rule"

            with patch.object(DarwinBridge, "is_compatible", return_value=True), \
                 patch("subprocess.run"), \
                 patch("os.path.exists", return_value=True), \
                 patch("os.remove"):
                removed = bridge.cleanup_all_rules()

            assert removed == 2
            assert len(_active_rules) == 0
        finally:
            _active_rules.clear()
            _active_rules.update(original)

    def test_cleanup_removes_pf_rules_file(self):
        """cleanup should remove the temporary PF rules file."""
        bridge = DarwinBridge()
        from backend.os_adapters.darwin_bridge import _active_rules

        original = _active_rules.copy()
        try:
            _active_rules.clear()

            with patch.object(DarwinBridge, "is_compatible", return_value=True), \
                 patch("subprocess.run"), \
                 patch("os.path.exists", return_value=True) as mock_exists, \
                 patch("os.remove") as mock_remove:
                bridge.cleanup_all_rules()

            mock_remove.assert_called_once()
        finally:
            _active_rules.clear()
            _active_rules.update(original)

    def test_cleanup_disables_pf(self):
        """cleanup should call `pfctl -Fr` to flush active rules."""
        bridge = DarwinBridge()
        from backend.os_adapters.darwin_bridge import _active_rules

        original = _active_rules.copy()
        try:
            _active_rules.clear()

            with patch.object(DarwinBridge, "is_compatible", return_value=True), \
                 patch("subprocess.run") as mock_run, \
                 patch("os.path.exists", return_value=False):
                mock_run.return_value = MagicMock(returncode=0)
                bridge.cleanup_all_rules()

            # Should have called "sudo pfctl -a com.vigilant -Fr"
            pfctl_calls = [c for c in mock_run.call_args_list
                           if "pfctl" in str(c) and "-Fr" in str(c)]
            assert len(pfctl_calls) >= 1
        finally:
            _active_rules.clear()
            _active_rules.update(original)


class TestCleanupEdgeCases:
    """Edge cases for both platforms."""

    def test_double_cleanup_is_idempotent(self):
        """Calling cleanup twice should not raise."""
        bridge = DarwinBridge()
        from backend.os_adapters.darwin_bridge import _active_rules

        original = _active_rules.copy()
        try:
            _active_rules[80] = "rule"

            with patch.object(DarwinBridge, "is_compatible", return_value=True), \
                 patch("subprocess.run"), \
                 patch("os.path.exists", return_value=False):
                bridge.cleanup_all_rules()
                bridge.cleanup_all_rules()  # second call
        finally:
            _active_rules.clear()
            _active_rules.update(original)

    def test_cleanup_on_non_compatible(self):
        """cleanup on non-compatible OS should return 0."""
        bridge = WindowsBridge()

        with patch.object(WindowsBridge, "is_compatible", return_value=False):
            removed = bridge.cleanup_all_rules()

        assert removed == 0
