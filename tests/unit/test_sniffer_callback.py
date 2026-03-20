"""
T1 — Unit Tests: SnifferProcess packet_callback

Tests packet classification, byte accumulation, and shared memory writes
using MockPacket objects (no real network capture).
"""

import sys
import struct
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, ".")

from backend.core.sniffer import (
    SnifferProcess,
    PORT_ENTRY_STRUCT,
    ENTRY_SIZE,
    read_port_entry,
)


# ---------------------------------------------------------------------------
# Mock Scapy layer classes (must match what the lazy import provides)
# ---------------------------------------------------------------------------

class FakeIP:
    """Mock for scapy.layers.inet.IP — used in haslayer() / __getitem__()."""
    pass
FakeIP.__name__ = "IP"

class FakeTCP:
    """Mock for scapy.layers.inet.TCP."""
    pass
FakeTCP.__name__ = "TCP"

class FakeUDP:
    """Mock for scapy.layers.inet.UDP."""
    pass
FakeUDP.__name__ = "UDP"


class TestSnifferPacketCallback:
    """Verify packet_callback accumulates bytes correctly."""

    @pytest.fixture(autouse=True)
    def mock_scapy_layers(self):
        """Pre-emptively mock scapy layers to avoid Windows route-reading crashes."""
        mock_inet = MagicMock()
        mock_inet.IP = FakeIP
        mock_inet.TCP = FakeTCP
        mock_inet.UDP = FakeUDP
        
        # Patch sys.modules so 'from scapy.layers.inet import ...' gets our mock
        with patch.dict("sys.modules", {"scapy.layers.inet": mock_inet}):
            yield

    def _make_sniffer(self):
        """Create a SnifferProcess without starting a real process."""
        # Call __init__ properly to avoid AttributeError in repr()
        s = SnifferProcess(interface=None)
        s._shm = None
        s._accum = {}
        return s

    def _make_packet(self, sport, dport, length, proto="TCP"):
        """Create a packet compatible with the Scapy-checking code paths."""
        from tests.conftest import MockPacket

        class LayerAwareMockPacket(MockPacket):
            def haslayer(self, layer_cls):
                name = getattr(layer_cls, "__name__", str(layer_cls))
                return name in self._layers

            def __getitem__(self, layer_cls):
                name = getattr(layer_cls, "__name__", str(layer_cls))
                if name in ("IP", "TCP", "UDP"):
                    return self
                raise KeyError(name)

        return LayerAwareMockPacket(sport, dport, length, proto)

    def test_tcp_inbound_accumulation(self):
        """TCP packet to dport=80 should accumulate bytes_in on port 80."""
        sniffer = self._make_sniffer()
        pkt = self._make_packet(54321, 80, 1500, "TCP")
        sniffer.packet_callback(pkt)

        assert 80 in sniffer._accum
        assert sniffer._accum[80][0] == 1500  # bytes_in

    def test_tcp_outbound_accumulation(self):
        """TCP packet from sport=443 should accumulate bytes_out on port 443."""
        sniffer = self._make_sniffer()
        pkt = self._make_packet(443, 54321, 2000, "TCP")
        sniffer.packet_callback(pkt)

        assert 443 in sniffer._accum
        assert sniffer._accum[443][1] == 2000  # bytes_out

    def test_udp_classification(self):
        """UDP packets should set protocol=1 in the accumulator."""
        sniffer = self._make_sniffer()
        pkt = self._make_packet(53, 54321, 512, "UDP")
        sniffer.packet_callback(pkt)

        assert 53 in sniffer._accum
        assert sniffer._accum[53][3] == 1  # protocol = UDP

    def test_multiple_packets_accumulate(self):
        """Multiple packets to same port should sum up."""
        sniffer = self._make_sniffer()

        for _ in range(5):
            pkt = self._make_packet(54321, 80, 1000, "TCP")
            sniffer.packet_callback(pkt)

        assert sniffer._accum[80][0] == 5000  # 5 * 1000 bytes_in

    def test_non_ip_packet_ignored(self):
        """A packet without IP layer should be silently skipped."""
        sniffer = self._make_sniffer()

        class NoIPPacket:
            def haslayer(self, _):
                return False

        sniffer.packet_callback(NoIPPacket())
        assert len(sniffer._accum) == 0

    def test_bidirectional_traffic(self):
        """A packet from port A→B increments bytes_out on A and bytes_in on B."""
        sniffer = self._make_sniffer()
        pkt = self._make_packet(80, 443, 750, "TCP")
        sniffer.packet_callback(pkt)

        assert sniffer._accum[80][1] == 750   # sport → bytes_out
        assert sniffer._accum[443][0] == 750  # dport → bytes_in


class TestSharedMemoryIO:
    """Verify read_port_entry against the struct layout."""

    def test_read_active_entry(self, populated_shm):
        """Active port entry should be read correctly."""
        entry = read_port_entry(populated_shm, 80)
        assert entry is not None
        port, bytes_in, bytes_out, pid, proto, active = entry
        assert port == 80
        assert bytes_in == 102400
        assert pid == 1234
        assert proto == 0
        assert active == 1

    def test_read_inactive_entry(self, fake_shm):
        """Inactive (zeroed) port should return None."""
        entry = read_port_entry(fake_shm, 12345)
        assert entry is None

    def test_read_udp_entry(self, populated_shm):
        """UDP port (53) should have protocol=1."""
        entry = read_port_entry(populated_shm, 53)
        assert entry is not None
        assert entry[4] == 1  # protocol = UDP
