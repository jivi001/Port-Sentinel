"""
T5 — Safety Tests: atexit firewall rule cleanup

Verifies that atexit hooks properly clean up all Sentinel_ firewall
rules on both Windows and macOS, preventing orphaned rules after crash.
"""

import sys
import atexit
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, ".")


class TestAtexitCleanupWindows:
    """Windows atexit cleanup."""

    def test_cleanup_called_removes_all_rules(self):
        """cleanup_all_rules should remove every Sentinel_ rule."""
        from backend.os_adapters import win32_bridge

        show_output = (
            "Rule Name:                            Sentinel_Block_Out_80\n"
            "Rule Name:                            Sentinel_Block_In_80\n"
            "Rule Name:                            Sentinel_Block_Out_443\n"
            "Rule Name:                            Sentinel_Block_In_443\n"
        )

        with patch.object(win32_bridge, "is_windows", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=show_output, stderr="")
            removed = win32_bridge.cleanup_all_rules()

        assert removed == 4

    def test_cleanup_handles_no_rules(self):
        """cleanup_all_rules with no Sentinel_ rules should return 0."""
        from backend.os_adapters import win32_bridge

        show_output = "Rule Name:                            WindowsFirewall\n"

        with patch.object(win32_bridge, "is_windows", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=show_output, stderr="")
            removed = win32_bridge.cleanup_all_rules()

        assert removed == 0

    def test_cleanup_survives_subprocess_error(self):
        """cleanup should not crash if subprocess fails (graceful degradation)."""
        from backend.os_adapters import win32_bridge
        from backend.core.exceptions import CleanupError

        with patch.object(win32_bridge, "is_windows", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("netsh crashed")

            with pytest.raises(CleanupError):
                win32_bridge.cleanup_all_rules()


class TestAtexitCleanupDarwin:
    """macOS atexit cleanup."""

    def test_cleanup_clears_active_rules(self):
        """cleanup_all_rules should clear _active_rules and disable pf."""
        from backend.os_adapters import darwin_bridge

        original = darwin_bridge._active_rules.copy()
        try:
            darwin_bridge._active_rules[80] = "block rule"
            darwin_bridge._active_rules[443] = "block rule"

            with patch("subprocess.run"), \
                 patch("os.path.exists", return_value=True), \
                 patch("os.remove"):
                removed = darwin_bridge.cleanup_all_rules()

            assert removed == 2
            assert len(darwin_bridge._active_rules) == 0
        finally:
            darwin_bridge._active_rules.clear()
            darwin_bridge._active_rules.update(original)

    def test_cleanup_removes_pf_rules_file(self):
        """cleanup should remove the temporary PF rules file."""
        from backend.os_adapters import darwin_bridge

        original = darwin_bridge._active_rules.copy()
        try:
            darwin_bridge._active_rules.clear()

            with patch("subprocess.run"), \
                 patch("os.path.exists", return_value=True) as mock_exists, \
                 patch("os.remove") as mock_remove:
                darwin_bridge.cleanup_all_rules()

            mock_remove.assert_called_once()
        finally:
            darwin_bridge._active_rules.clear()
            darwin_bridge._active_rules.update(original)

    def test_cleanup_disables_pf(self):
        """cleanup should call `pfctl -d` to disable packet filter."""
        from backend.os_adapters import darwin_bridge

        original = darwin_bridge._active_rules.copy()
        try:
            darwin_bridge._active_rules.clear()

            with patch("subprocess.run") as mock_run, \
                 patch("os.path.exists", return_value=False):
                mock_run.return_value = MagicMock(returncode=0)
                darwin_bridge.cleanup_all_rules()

            # Should have called "sudo pfctl -d"
            pfctl_calls = [c for c in mock_run.call_args_list
                           if "pfctl" in str(c) and "-d" in str(c)]
            assert len(pfctl_calls) >= 1
        finally:
            darwin_bridge._active_rules.clear()
            darwin_bridge._active_rules.update(original)


class TestCleanupEdgeCases:
    """Edge cases for both platforms."""

    def test_double_cleanup_is_idempotent(self):
        """Calling cleanup twice should not raise."""
        from backend.os_adapters import darwin_bridge

        original = darwin_bridge._active_rules.copy()
        try:
            darwin_bridge._active_rules[80] = "rule"

            with patch("subprocess.run"), \
                 patch("os.path.exists", return_value=False):
                darwin_bridge.cleanup_all_rules()
                darwin_bridge.cleanup_all_rules()  # second call
        finally:
            darwin_bridge._active_rules.clear()
            darwin_bridge._active_rules.update(original)

    def test_cleanup_on_non_windows(self):
        """cleanup on non-Windows should return 0."""
        from backend.os_adapters import win32_bridge

        with patch.object(win32_bridge, "is_windows", return_value=False):
            removed = win32_bridge.cleanup_all_rules()

        assert removed == 0
