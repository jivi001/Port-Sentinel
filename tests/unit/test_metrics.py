"""
T1 — Unit Tests: PortMetrics, SlidingWindowCache, TrafficAccumulator

Tests delta calculation, overflow guard, zero-traffic edge case,
sliding window eviction, and port-table serialisation.
"""

import sys
import time
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, ".")

from backend.core.metrics import (
    PortMetrics,
    SlidingWindowCache,
    TrafficAccumulator,
    PortSnapshot,
    MAX_WINDOW_ENTRIES,
)


# ===================================================================
# PortMetrics.calculate_delta
# ===================================================================

class TestPortMetricsDelta:
    """Verify KB/s calculation from consecutive byte counter snapshots."""

    def test_first_call_returns_zero(self, port_metrics):
        """First snapshot should return (0.0, 0.0) — no previous data."""
        kb_in, kb_out = port_metrics.calculate_delta(80, 1024, 512, current_time=100.0)
        assert kb_in == 0.0
        assert kb_out == 0.0

    def test_normal_delta(self, port_metrics):
        """Normal case: 10240 bytes in 1 second = 10 KB/s."""
        port_metrics.calculate_delta(80, 0, 0, current_time=100.0)
        kb_in, kb_out = port_metrics.calculate_delta(80, 10240, 5120, current_time=101.0)
        assert kb_in == 10.0
        assert kb_out == 5.0

    def test_zero_traffic(self, port_metrics):
        """No bytes transferred → 0.0 KB/s, no division-by-zero crash."""
        port_metrics.calculate_delta(80, 1000, 500, current_time=100.0)
        kb_in, kb_out = port_metrics.calculate_delta(80, 1000, 500, current_time=101.0)
        assert kb_in == 0.0
        assert kb_out == 0.0

    def test_zero_elapsed_time(self, port_metrics):
        """Same timestamp on two calls → (0.0, 0.0), no ZeroDivisionError."""
        port_metrics.calculate_delta(80, 0, 0, current_time=100.0)
        kb_in, kb_out = port_metrics.calculate_delta(80, 10240, 5120, current_time=100.0)
        assert kb_in == 0.0
        assert kb_out == 0.0

    def test_overflow_guard(self, port_metrics):
        """Byte counter wrap at 2^64 boundary should produce positive delta."""
        max_val = 2**64 - 1
        port_metrics.calculate_delta(80, max_val - 100, max_val - 50, current_time=100.0)
        # After wrap: current = 200 (bytes_in), 150 (bytes_out)
        kb_in, kb_out = port_metrics.calculate_delta(80, 200, 150, current_time=101.0)
        # delta_in = 200 + (2^64 - (max_val-100)) = 200 + 101 = 301
        assert kb_in > 0.0
        assert kb_out > 0.0

    def test_multiple_ports_independent(self, port_metrics):
        """Deltas for different ports should not interfere with each other."""
        port_metrics.calculate_delta(80, 0, 0, current_time=100.0)
        port_metrics.calculate_delta(443, 0, 0, current_time=100.0)

        kb80_in, _ = port_metrics.calculate_delta(80, 10240, 0, current_time=101.0)
        kb443_in, _ = port_metrics.calculate_delta(443, 20480, 0, current_time=101.0)

        assert kb80_in == 10.0
        assert kb443_in == 20.0

    def test_fractional_rates(self, port_metrics):
        """Sub-KB traffic should produce valid fractional KB/s."""
        port_metrics.calculate_delta(80, 0, 0, current_time=100.0)
        kb_in, _ = port_metrics.calculate_delta(80, 512, 0, current_time=101.0)
        assert kb_in == 0.5

    def test_multi_second_interval(self, port_metrics):
        """5 seconds elapsed → rate should be bytes / 5 / 1024."""
        port_metrics.calculate_delta(80, 0, 0, current_time=100.0)
        kb_in, _ = port_metrics.calculate_delta(80, 51200, 0, current_time=105.0)
        assert kb_in == 10.0  # 51200 / 1024 / 5

    def test_reset_single_port(self, port_metrics):
        """Resetting a port should make next call return zero."""
        port_metrics.calculate_delta(80, 1000, 500, current_time=100.0)
        port_metrics.reset(port=80)
        kb_in, kb_out = port_metrics.calculate_delta(80, 2000, 1000, current_time=101.0)
        assert kb_in == 0.0
        assert kb_out == 0.0

    def test_reset_all_ports(self, port_metrics):
        """Resetting all ports should clear all state."""
        port_metrics.calculate_delta(80, 1000, 500, current_time=100.0)
        port_metrics.calculate_delta(443, 2000, 1000, current_time=100.0)
        port_metrics.reset()
        kb_in, _ = port_metrics.calculate_delta(80, 2000, 0, current_time=101.0)
        assert kb_in == 0.0


# ===================================================================
# SlidingWindowCache
# ===================================================================

class TestSlidingWindowCache:
    """Verify cache add, lookup, eviction, and memory bounds."""

    def _make_snapshot(self, port=80, ts=None, kb_in=1.0, kb_out=0.5):
        return PortSnapshot(
            timestamp=ts or time.time(),
            port=port, pid=1234, app_name="test",
            kb_s_in=kb_in, kb_s_out=kb_out,
            protocol="TCP", direction="both",
        )

    def test_add_and_get(self, sliding_cache):
        """Added snapshot should appear in get_history."""
        snap = self._make_snapshot(ts=time.time())
        sliding_cache.add(snap)
        history = sliding_cache.get_history(80)
        assert len(history) == 1
        assert history[0].port == 80

    def test_empty_history(self, sliding_cache):
        """Untracked port should return empty list."""
        assert sliding_cache.get_history(9999) == []

    def test_maxlen_bound(self):
        """Cache should never exceed max_entries per port."""
        cache = SlidingWindowCache(max_entries=10)
        for i in range(20):
            cache.add(self._make_snapshot(ts=float(i)))
        assert len(cache.get_history(80)) == 10

    def test_evict_stale(self, sliding_cache):
        """Entries older than max_age should be evicted."""
        old_time = time.time() - 100_000  # ~27 hours ago
        now = time.time()
        sliding_cache.add(self._make_snapshot(ts=old_time))
        sliding_cache.add(self._make_snapshot(ts=now))
        evicted = sliding_cache.evict_stale(max_age_seconds=86_400)
        assert evicted == 1
        assert len(sliding_cache.get_history(80)) == 1

    def test_get_history_with_seconds_filter(self, sliding_cache):
        """Seconds filter should only return recent entries."""
        now = time.time()
        sliding_cache.add(self._make_snapshot(ts=now - 120))
        sliding_cache.add(self._make_snapshot(ts=now - 30))
        sliding_cache.add(self._make_snapshot(ts=now))
        recent = sliding_cache.get_history(80, seconds=60)
        assert len(recent) == 2  # only last 60s

    def test_port_count(self, sliding_cache):
        """port_count should return number of distinct ports tracked."""
        sliding_cache.add(self._make_snapshot(port=80))
        sliding_cache.add(self._make_snapshot(port=443))
        sliding_cache.add(self._make_snapshot(port=80))
        assert sliding_cache.port_count() == 2

    def test_total_entries(self, sliding_cache):
        """total_entries counts across all ports."""
        sliding_cache.add(self._make_snapshot(port=80))
        sliding_cache.add(self._make_snapshot(port=80))
        sliding_cache.add(self._make_snapshot(port=443))
        assert sliding_cache.total_entries() == 3

    def test_clear(self, sliding_cache):
        """clear should remove everything."""
        sliding_cache.add(self._make_snapshot(port=80))
        sliding_cache.clear()
        assert sliding_cache.port_count() == 0
        assert sliding_cache.total_entries() == 0


# ===================================================================
# TrafficAccumulator
# ===================================================================

class TestTrafficAccumulator:
    """Integration of PortMetrics + SlidingWindowCache."""

    def test_process_and_get_table(self, accumulator):
        """process_port_data should produce a retrievable port table entry."""
        accumulator.process_port_data(80, 0, 0, pid=1234, protocol=0, timestamp=100.0)
        accumulator.process_port_data(80, 10240, 5120, pid=1234, protocol=0, timestamp=101.0)
        table = accumulator.get_port_table()
        assert len(table) == 1
        assert table[0]["port"] == 80
        assert table[0]["kb_s_in"] == 10.0
        assert table[0]["protocol"] == "TCP"

    def test_multiple_ports_in_table(self, accumulator):
        """Table should contain one row per port, sorted by port number."""
        for port in [443, 80, 8080]:
            accumulator.process_port_data(port, 0, 0, pid=100, protocol=0, timestamp=100.0)
            accumulator.process_port_data(port, 1024, 512, pid=100, protocol=0, timestamp=101.0)
        table = accumulator.get_port_table()
        assert len(table) == 3
        assert [r["port"] for r in table] == [80, 443, 8080]

    def test_udp_protocol_label(self, accumulator):
        """Protocol 1 should map to 'UDP'."""
        accumulator.process_port_data(53, 0, 0, pid=999, protocol=1, timestamp=100.0)
        accumulator.process_port_data(53, 2048, 1024, pid=999, protocol=1, timestamp=101.0)
        table = accumulator.get_port_table()
        assert table[0]["protocol"] == "UDP"

    def test_system_pid_app_names(self, accumulator):
        """PID 0, 1, 4 should all resolve to 'System'."""
        for pid in [0, 1, 4]:
            accumulator.process_port_data(80 + pid, 0, 0, pid=pid, protocol=0, timestamp=100.0)
        table = accumulator.get_port_table()
        for row in table:
            assert row["app_name"] == "System"

    def test_cleanup_evicts_stale(self, accumulator):
        """cleanup() should evict old entries without crashing."""
        accumulator.process_port_data(80, 0, 0, pid=1234, protocol=0, timestamp=1.0)
        accumulator.cleanup()  # should not raise
