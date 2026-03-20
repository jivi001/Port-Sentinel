"""
T1 — Unit Tests: Port-to-PID mapping and app name resolution

Tests the TrafficAccumulator._resolve_app_name logic and
the PID→app-name cache.
"""

import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, ".")

from backend.core.metrics import TrafficAccumulator


class TestAppNameResolution:
    """Verify PID → application name mapping."""

    def test_system_pid_zero(self):
        """PID 0 → 'System' (kernel)."""
        acc = TrafficAccumulator()
        name = acc._resolve_app_name(0)
        assert name == "System"

    def test_system_pid_one(self):
        """PID 1 → 'System' (launchd on macOS)."""
        acc = TrafficAccumulator()
        name = acc._resolve_app_name(1)
        assert name == "System"

    def test_system_pid_four(self):
        """PID 4 → 'System' (Windows System process)."""
        acc = TrafficAccumulator()
        name = acc._resolve_app_name(4)
        assert name == "System"

    def test_normal_pid_resolves(self):
        """Regular PID should call psutil.Process and return name."""
        with patch("backend.core.metrics.psutil") as mock_psutil:
            mock_proc = MagicMock()
            mock_proc.name.return_value = "firefox.exe"
            mock_psutil.Process.return_value = mock_proc
            mock_psutil.NoSuchProcess = Exception
            mock_psutil.AccessDenied = PermissionError
            mock_psutil.ZombieProcess = Exception

            acc = TrafficAccumulator()
            name = acc._resolve_app_name(5678)
        assert name == "firefox.exe"

    def test_no_such_process_returns_unknown(self):
        """Stale PID that no longer exists → 'Unknown'."""
        with patch("backend.core.metrics.psutil") as mock_psutil:
            mock_psutil.NoSuchProcess = Exception
            mock_psutil.AccessDenied = PermissionError
            mock_psutil.ZombieProcess = Exception
            mock_psutil.Process.side_effect = Exception("no such process")

            acc = TrafficAccumulator()
            acc._app_name_cache.clear()
            name = acc._resolve_app_name(99999)
        assert name == "Unknown"

    def test_cache_hit_avoids_psutil_call(self):
        """Cached PID should not call psutil.Process again."""
        acc = TrafficAccumulator()
        acc._app_name_cache[1234] = "cached_app"
        name = acc._resolve_app_name(1234)
        assert name == "cached_app"

    def test_cache_populated_on_first_call(self):
        """First resolution should populate the cache."""
        with patch("backend.core.metrics.psutil") as mock_psutil:
            mock_proc = MagicMock()
            mock_proc.name.return_value = "notepad.exe"
            mock_psutil.Process.return_value = mock_proc
            mock_psutil.NoSuchProcess = Exception
            mock_psutil.AccessDenied = PermissionError
            mock_psutil.ZombieProcess = Exception

            acc = TrafficAccumulator()
            acc._resolve_app_name(7777)
        assert 7777 in acc._app_name_cache
        assert acc._app_name_cache[7777] == "notepad.exe"
