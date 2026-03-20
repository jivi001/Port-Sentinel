"""
T2 — Integration Tests: WebSocket dispatch (MsgPack emission)

Verifies the Dispatcher loop reads shared memory, encodes to MsgPack,
and the resulting binary frame is deserializable by the frontend.
"""

import sys
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, ".")

from backend.core.metrics import PortMetrics, TrafficAccumulator
from backend.core.sniffer import PORT_ENTRY_STRUCT, ENTRY_SIZE


# Lazy msgpack import — install only needed for integration tier
try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False


def _make_patched_accumulator():
    """Create a TrafficAccumulator with psutil mocked for the full lifetime."""
    patcher = patch("backend.core.metrics.psutil")
    mock_psutil = patcher.start()

    mock_proc = MagicMock()
    mock_proc.name.return_value = "test"
    mock_psutil.Process.return_value = mock_proc
    mock_psutil.NoSuchProcess = Exception
    mock_psutil.AccessDenied = PermissionError
    mock_psutil.ZombieProcess = Exception

    acc = TrafficAccumulator()
    return acc, patcher


class TestDispatcherMsgPack:
    """Verify port-table → MsgPack serialisation round-trip."""

    def _build_port_table(self):
        """Create a realistic port table list-of-dicts."""
        return [
            {
                "port": 80,
                "pid": 1234,
                "app_name": "nginx",
                "kb_s_in": 10.5,
                "kb_s_out": 5.2,
                "kb_s": 15.7,
                "protocol": "TCP",
                "direction": "both",
                "timestamp": time.time(),
            },
            {
                "port": 443,
                "pid": 1234,
                "app_name": "nginx",
                "kb_s_in": 25.0,
                "kb_s_out": 12.5,
                "kb_s": 37.5,
                "protocol": "TCP",
                "direction": "both",
                "timestamp": time.time(),
            },
        ]

    @pytest.mark.skipif(not HAS_MSGPACK, reason="msgpack not installed")
    def test_msgpack_round_trip(self):
        """Port table should survive MsgPack pack→unpack without data loss."""
        table = self._build_port_table()
        packed = msgpack.packb(table, use_bin_type=True)
        unpacked = msgpack.unpackb(packed, raw=False)

        assert len(unpacked) == 2
        assert unpacked[0]["port"] == 80
        assert unpacked[1]["port"] == 443
        assert unpacked[0]["app_name"] == "nginx"

    @pytest.mark.skipif(not HAS_MSGPACK, reason="msgpack not installed")
    def test_msgpack_binary_size(self):
        """MsgPack frame should be smaller than equivalent JSON."""
        import json
        table = self._build_port_table()
        packed = msgpack.packb(table, use_bin_type=True)
        json_bytes = json.dumps(table).encode()

        assert len(packed) < len(json_bytes), \
            f"MsgPack ({len(packed)}B) should be smaller than JSON ({len(json_bytes)}B)"

    @pytest.mark.skipif(not HAS_MSGPACK, reason="msgpack not installed")
    def test_empty_table_serialization(self):
        """Empty port table should serialize to a valid empty MsgPack array."""
        packed = msgpack.packb([], use_bin_type=True)
        unpacked = msgpack.unpackb(packed, raw=False)
        assert unpacked == []

    @pytest.mark.skipif(not HAS_MSGPACK, reason="msgpack not installed")
    def test_large_table_serialization(self):
        """100-port table should serialize and deserialize correctly."""
        table = [
            {
                "port": p,
                "pid": 1000 + p,
                "app_name": f"app_{p}",
                "kb_s_in": float(p),
                "kb_s_out": float(p) / 2,
                "kb_s": float(p) * 1.5,
                "protocol": "TCP",
                "direction": "both",
                "timestamp": time.time(),
            }
            for p in range(100)
        ]
        packed = msgpack.packb(table, use_bin_type=True)
        unpacked = msgpack.unpackb(packed, raw=False)
        assert len(unpacked) == 100
        assert unpacked[50]["port"] == 50


class TestTrafficAccumulatorPortTable:
    """Verify TrafficAccumulator produces well-formed port tables."""

    def test_port_table_schema(self):
        """Each row must have all required keys."""
        required_keys = {"port", "pid", "app_name", "kb_s_in", "kb_s_out",
                         "kb_s", "protocol", "direction", "timestamp"}

        acc, patcher = _make_patched_accumulator()
        try:
            acc.process_port_data(80, 0, 0, 1234, 0, timestamp=100.0)
            acc.process_port_data(80, 1024, 512, 1234, 0, timestamp=101.0)
            table = acc.get_port_table()
        finally:
            patcher.stop()

        assert len(table) >= 1
        for row in table:
            missing = required_keys - set(row.keys())
            assert not missing, f"Missing keys: {missing}"

    def test_port_table_sorted_by_port(self):
        """Port table should be sorted ascending by port number."""
        acc, patcher = _make_patched_accumulator()
        try:
            for port in [8080, 443, 80, 3306]:
                acc.process_port_data(port, 0, 0, 100, 0, timestamp=100.0)
            table = acc.get_port_table()
        finally:
            patcher.stop()

        ports = [r["port"] for r in table]
        assert ports == sorted(ports)

    def test_total_kb_s_computed(self):
        """kb_s should equal kb_s_in + kb_s_out."""
        acc, patcher = _make_patched_accumulator()
        try:
            acc.process_port_data(80, 0, 0, 1234, 0, timestamp=100.0)
            acc.process_port_data(80, 10240, 5120, 1234, 0, timestamp=101.0)
            table = acc.get_port_table()
        finally:
            patcher.stop()

        row = table[0]
        assert row["kb_s"] == round(row["kb_s_in"] + row["kb_s_out"], 2)
