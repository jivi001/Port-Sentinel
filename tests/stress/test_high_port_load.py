"""
T4 — Stress Tests: High port load

Verifies that processing 100 simultaneous ports stays under
the p95 latency budget (< 50ms per dispatch cycle).
"""

import sys
import time
import statistics
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, ".")

from backend.core.metrics import TrafficAccumulator


# Latency budget (milliseconds)
P95_BUDGET_MS = 50
DISPATCH_CYCLES = 100
PORT_COUNT = 100


def _make_accumulator_with_patcher():
    """Create accumulator with psutil mock that persists beyond __init__."""
    patcher = patch("backend.core.metrics.psutil")
    mock_psutil = patcher.start()

    mock_proc = MagicMock()
    mock_proc.name.return_value = "stress_app"
    mock_psutil.Process.return_value = mock_proc
    mock_psutil.NoSuchProcess = Exception
    mock_psutil.AccessDenied = PermissionError
    mock_psutil.ZombieProcess = Exception

    return TrafficAccumulator(), patcher


class TestHighPortLoad:
    """Measure dispatch latency under realistic port volume."""

    def test_100_port_p95_under_budget(self):
        """
        Simulate 100 ports x 100 cycles.

        Acceptance criterion: p95 cycle time < 50ms.
        """
        acc, patcher = _make_accumulator_with_patcher()
        try:
            # Seed initial counters
            t0 = 100.0
            for port in range(PORT_COUNT):
                acc.process_port_data(port, 0, 0, pid=1000 + port, protocol=0, timestamp=t0)

            latencies_ms = []

            for cycle in range(DISPATCH_CYCLES):
                t_now = t0 + 1.0 + (cycle * 0.5)
                start = time.perf_counter()

                # Simulate traffic update for all ports
                for port in range(PORT_COUNT):
                    bytes_delta = (port + 1) * 1024 * (cycle + 1)
                    acc.process_port_data(
                        port, bytes_delta, bytes_delta // 2,
                        pid=1000 + port, protocol=0, timestamp=t_now,
                    )

                # Get the full port table (simulates dispatch)
                table = acc.get_port_table()

                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies_ms.append(elapsed_ms)

            p95 = sorted(latencies_ms)[int(len(latencies_ms) * 0.95)]
            p50 = statistics.median(latencies_ms)
            mean = statistics.mean(latencies_ms)

            print(f"\n{'='*50}")
            print(f"Port Load Stress Test Results")
            print(f"  Ports: {PORT_COUNT}, Cycles: {DISPATCH_CYCLES}")
            print(f"  Mean:  {mean:.2f}ms")
            print(f"  p50:   {p50:.2f}ms")
            print(f"  p95:   {p95:.2f}ms")
            print(f"  Max:   {max(latencies_ms):.2f}ms")
            print(f"  Budget (p95): {P95_BUDGET_MS}ms")
            print(f"{'='*50}")

            assert p95 < P95_BUDGET_MS, \
                f"p95 latency {p95:.2f}ms exceeds budget {P95_BUDGET_MS}ms"
        finally:
            patcher.stop()

    def test_table_size_under_load(self):
        """Port table should contain all 100 ports after processing."""
        acc, patcher = _make_accumulator_with_patcher()
        try:
            for port in range(PORT_COUNT):
                acc.process_port_data(port, 0, 0, pid=1000 + port, protocol=0, timestamp=100.0)
                acc.process_port_data(port, 10240, 5120, pid=1000 + port, protocol=0, timestamp=101.0)

            table = acc.get_port_table()
            assert len(table) >= PORT_COUNT, \
                f"Expected {PORT_COUNT} ports, got {len(table)}"
        finally:
            patcher.stop()

    def test_concurrent_port_updates_no_crash(self):
        """Rapidly updating the same port should not cause errors."""
        acc, patcher = _make_accumulator_with_patcher()
        try:
            for i in range(1000):
                acc.process_port_data(80, i * 100, i * 50, pid=1234, protocol=0, timestamp=100.0 + i * 0.001)

            table = acc.get_port_table()
            ports = [r["port"] for r in table]
            assert 80 in ports
        finally:
            patcher.stop()

    def test_sparkline_history_under_load(self):
        """Sliding window should hold data for 100 ports over 60 seconds."""
        acc, patcher = _make_accumulator_with_patcher()
        try:
            # 60 seconds of data, 1 update per second per port
            t0 = time.time() - 60
            for t in range(60):
                for port in range(PORT_COUNT):
                    acc.process_port_data(
                        port, t * 1024, t * 512,
                        pid=1000 + port, protocol=0,
                        timestamp=t0 + t,
                    )

            # Verify sparkline data exists
            history = acc.cache.get_history(50, seconds=65)
            assert len(history) > 0, "No sparkline history for port 50"
        finally:
            patcher.stop()
