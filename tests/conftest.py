"""
Sentinel — Shared test fixtures (conftest.py)

Provides mock objects, sample data, and helper functions used across all test tiers.
"""

import sys
import os
import struct
import time
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from backend.core.sniffer import PORT_ENTRY_STRUCT, ENTRY_SIZE, SHM_SIZE, MAX_PORTS
from backend.core.metrics import PortMetrics, SlidingWindowCache, TrafficAccumulator, PortSnapshot


# ---------------------------------------------------------------------------
# Fake SharedMemory (dict-backed, no OS resources)
# ---------------------------------------------------------------------------

class FakeSharedMemory:
    """In-process byte-buffer that mimics multiprocessing.shared_memory.SharedMemory."""

    def __init__(self, name: str = "sentinel_traffic_shm", size: int = SHM_SIZE):
        self.name = name
        self.size = size
        self._data = bytearray(size)
        self.buf = memoryview(self._data)

    def close(self):
        pass

    def unlink(self):
        pass


@pytest.fixture
def fake_shm():
    """Yield a clean FakeSharedMemory instance."""
    return FakeSharedMemory()


# ---------------------------------------------------------------------------
# Port entry helpers
# ---------------------------------------------------------------------------

def write_port_entry(shm, port: int, bytes_in: int, bytes_out: int,
                     pid: int, protocol: int = 0, active: int = 1):
    """Write a single port entry to the given shared-memory buffer."""
    offset = port * ENTRY_SIZE
    data = PORT_ENTRY_STRUCT.pack(port, bytes_in, bytes_out, pid, protocol, active)
    shm.buf[offset:offset + ENTRY_SIZE] = data


def read_port_entry_raw(shm, port: int):
    """Read and unpack one port entry from a shared-memory buffer."""
    offset = port * ENTRY_SIZE
    return PORT_ENTRY_STRUCT.unpack(bytes(shm.buf[offset:offset + ENTRY_SIZE]))


@pytest.fixture
def populated_shm(fake_shm):
    """A FakeSharedMemory with 5 port entries pre-written."""
    entries = [
        # port, bytes_in, bytes_out, pid, proto, active
        (80,   102400, 51200, 1234, 0, 1),
        (443,  204800, 102400, 1234, 0, 1),
        (8080, 10240,  5120,  5678, 0, 1),
        (53,   2048,   1024,  999,  1, 1),
        (3306, 51200,  25600, 2222, 0, 1),
    ]
    for entry in entries:
        write_port_entry(fake_shm, *entry)
    return fake_shm


# ---------------------------------------------------------------------------
# Metrics fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def port_metrics():
    """Fresh PortMetrics instance."""
    return PortMetrics()


@pytest.fixture
def sliding_cache():
    """Fresh SlidingWindowCache with default max_entries."""
    return SlidingWindowCache()


@pytest.fixture
def accumulator():
    """Fresh TrafficAccumulator with mocked psutil."""
    with patch("backend.core.metrics.psutil") as mock_psutil:
        mock_proc = MagicMock()
        mock_proc.name.return_value = "test_app"
        mock_psutil.Process.return_value = mock_proc
        mock_psutil.NoSuchProcess = Exception
        mock_psutil.AccessDenied = PermissionError
        mock_psutil.ZombieProcess = Exception
        acc = TrafficAccumulator()
        yield acc


# ---------------------------------------------------------------------------
# Mock Scapy packet constructors
# ---------------------------------------------------------------------------

class MockPacket:
    """Lightweight mock that mimics a Scapy packet with IP + TCP/UDP layers."""

    def __init__(self, sport: int, dport: int, payload_len: int, proto: str = "TCP"):
        self._layers = {"IP": True}
        self.sport = sport
        self.dport = dport
        self._payload_len = payload_len
        self._proto = proto
        if proto == "TCP":
            self._layers["TCP"] = True
        elif proto == "UDP":
            self._layers["UDP"] = True

    def haslayer(self, layer_cls):
        name = layer_cls if isinstance(layer_cls, str) else getattr(layer_cls, "__name__", str(layer_cls))
        return name in self._layers

    def __getitem__(self, layer_cls):
        name = layer_cls if isinstance(layer_cls, str) else getattr(layer_cls, "__name__", str(layer_cls))
        if name == "IP":
            return self
        if name in ("TCP", "UDP"):
            return self  # sport/dport available on self
        raise KeyError(name)

    def __len__(self):
        return self._payload_len


@pytest.fixture
def make_packet():
    """Factory fixture for creating MockPackets."""
    def _make(sport=443, dport=54321, payload=1024, proto="TCP"):
        return MockPacket(sport, dport, payload, proto)
    return _make


# ---------------------------------------------------------------------------
# System PID sets (for safety tests)
# ---------------------------------------------------------------------------

SYSTEM_PIDS_WINDOWS = frozenset({0, 4})
SYSTEM_PIDS_DARWIN = frozenset({0, 1})
SYSTEM_PIDS_ALL = SYSTEM_PIDS_WINDOWS | SYSTEM_PIDS_DARWIN
