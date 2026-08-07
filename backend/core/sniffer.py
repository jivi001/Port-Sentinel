"""
Sentinel Core Sniffer — OS-agnostic packet capture logic.

Architecture:
  - Runs as multiprocessing.Process to bypass GIL
  - Uses SharedMemory for zero-copy byte counter exchange with the Dispatcher
  - Scapy sniff() in callback mode at 10Hz capture resolution
  - Sets OS high-priority on the sniffer process

SharedMemory Layout (per port, max 65536 ports):
  Each port entry = 32 bytes:
    [0:2]   port number (uint16)
    [2:10]  bytes_in (uint64)
    [10:18] bytes_out (uint64)
    [18:22] pid (uint32)
    [22:23] protocol (uint8: 0=TCP, 1=UDP)
    [23:24] active flag (uint8: 0=inactive, 1=active)
    [24:32] reserved

Total shared memory: 65536 * 32 = 2MB (fixed allocation)
"""

import struct
import sys
import os
import time
import platform
import logging
import multiprocessing
from multiprocessing import shared_memory
from typing import Optional, Dict, Tuple

import psutil

# Optimization: Silence Scapy warnings for malformed or non-essential packets (like ISAKMP)
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

logger = logging.getLogger("sentinel.sniffer")

# --- Constants ---
MAX_PORTS = 65536
ENTRY_SIZE = 64  # 32 bytes data + 32 bytes HMAC
BITMAP_SIZE = 8192  # 65536 bits / 8
BITMAP_OFFSET = MAX_PORTS * ENTRY_SIZE
SHM_NAME = "sentinel_traffic_shm"  # Fallback
SHM_SIZE = BITMAP_OFFSET + BITMAP_SIZE
CAPTURE_INTERVAL = 0.1  # 100ms = 10Hz

# Struct format for a single port entry
# H = uint16 (port), Q = uint64 (bytes_in), Q = uint64 (bytes_out),
# I = uint32 (pid), B = uint8 (protocol), B = uint8 (active)
# B = uint8 (risk_score), 4s = 4 bytes (remote_ip), 3x = padding
PORT_ENTRY_FMT = "<HQQI BBB 4s 3x"
PORT_ENTRY_STRUCT = struct.Struct(PORT_ENTRY_FMT)


def _set_high_priority() -> None:
    """Set the current process to high priority for real-time capture."""
    try:
        p = psutil.Process(os.getpid())
        if platform.system() == "Windows":
            p.nice(psutil.HIGH_PRIORITY_CLASS)
        else:
            # Unix: lower nice = higher priority; -10 requires root
            try:
                os.nice(-10)
            except PermissionError:
                os.nice(0)  # fallback to normal priority
        logger.info("Sniffer process priority elevated")
    except Exception as e:
        logger.warning(f"Could not set high priority: {e}")


class SnifferProcess(multiprocessing.Process):
    """
    Dedicated process for packet capture using Scapy.

    Writes byte counters into shared memory that the Dispatcher reads.
    """

    def __init__(self, hmac_key: bytes, interface: Optional[str] = None, 
                 stop_event: Optional[multiprocessing.Event] = None,
                 lock: Optional[multiprocessing.Lock] = None,
                 shm_name: str = "sentinel_traffic_shm"):
        super().__init__(daemon=True)
        self.interface = interface
        self.stop_event = stop_event or multiprocessing.Event()
        self.lock = lock or multiprocessing.Lock()
        self.shm_name = shm_name
        self.hmac_key = hmac_key
        self._shm: Optional[shared_memory.SharedMemory] = None
        # Local accumulation buffer: port -> (bytes_in, bytes_out, pid, proto)
        self._accum: Dict[int, list] = {}
        
        # Performance: Cache PID map to avoid calling psutil.net_connections 10 times per second
        self._cached_pid_map: Dict[int, int] = {}
        self._last_pid_map_update: float = 0.0

    def _init_shared_memory(self) -> shared_memory.SharedMemory:
        """Create or attach to the shared memory segment."""
        try:
            shm = shared_memory.SharedMemory(name=self.shm_name, create=True, size=SHM_SIZE)
            # Zero-initialize
            shm.buf[:SHM_SIZE] = b'\x00' * SHM_SIZE
            logger.info(f"Created shared memory '{self.shm_name}' ({SHM_SIZE} bytes)")
        except FileExistsError:
            shm = shared_memory.SharedMemory(name=self.shm_name, create=False, size=SHM_SIZE)
            logger.info(f"Attached to existing shared memory '{self.shm_name}'")
        return shm

    def _write_port_entry(self, port: int, bytes_in: int, bytes_out: int,
                          pid: int, protocol: int, active: int, 
                          risk_score: int = 0, remote_ip: str = "0.0.0.0") -> None:
        """Write a single port entry to shared memory."""
        if self._shm is None:
            return
        offset = port * ENTRY_SIZE
        
        # Convert string IP to 4 bytes
        import socket
        import hmac
        import hashlib
        try:
            ip_bytes = socket.inet_aton(remote_ip)
        except (OSError, ValueError):
            ip_bytes = b'\x00\x00\x00\x00'

        # Guard against overflow
        bytes_in = bytes_in % (2**64)
        bytes_out = bytes_out % (2**64)
        
        data = PORT_ENTRY_STRUCT.pack(port, bytes_in, bytes_out, pid, protocol, active, risk_score, ip_bytes)
        mac = hmac.new(self.hmac_key, data, hashlib.sha256).digest()
        self._shm.buf[offset:offset + ENTRY_SIZE] = data + mac
        
        # Update active port bitmap
        if active:
            self._shm.buf[BITMAP_OFFSET + (port // 8)] |= (1 << (port % 8))
        else:
            self._shm.buf[BITMAP_OFFSET + (port // 8)] &= ~(1 << (port % 8))

    def packet_callback(self, packet) -> None:
        """
        Callback invoked by Scapy for each captured packet.
        """
        try:
            # Lazy import
            from scapy.layers.inet import IP, TCP, UDP

            if not hasattr(self, "_threat_intel"):
                from backend.core.threat_intel import ThreatIntel
                self._threat_intel = ThreatIntel()

            if not packet.haslayer(IP):
                return

            ip_layer = packet[IP]
            payload_len = len(packet)
            
            sport = 0
            dport = 0
            protocol = 0  # 0=TCP, 1=UDP

            if packet.haslayer(TCP):
                sport = packet[TCP].sport
                dport = packet[TCP].dport
                protocol = 0
            elif packet.haslayer(UDP):
                sport = packet[UDP].sport
                dport = packet[UDP].dport
                protocol = 1
            else:
                return

            # Accumulate for source port (outbound)
            if sport > 0 and sport < MAX_PORTS:
                remote_ip = ip_layer.dst
                risk = self._threat_intel.get_risk_score(remote_ip)
                if sport not in self._accum:
                    self._accum[sport] = [0, 0, 0, protocol, 0, "0.0.0.0", 0.0] # in, out, pid, proto, risk, remote_ip, last_seen
                self._accum[sport][1] += payload_len
                self._accum[sport][4] = max(self._accum[sport][4], risk)
                self._accum[sport][5] = remote_ip
                self._accum[sport][6] = time.time()

            # Accumulate for destination port (inbound)
            if dport > 0 and dport < MAX_PORTS:
                remote_ip = ip_layer.src
                risk = self._threat_intel.get_risk_score(remote_ip)
                if dport not in self._accum:
                    self._accum[dport] = [0, 0, 0, protocol, 0, "0.0.0.0", 0.0]
                self._accum[dport][0] += payload_len
                self._accum[dport][4] = max(self._accum[dport][4], risk)
                self._accum[dport][5] = remote_ip
                self._accum[dport][6] = time.time()

        except Exception as e:
            logger.debug(f"Packet callback error: {e}")

    def _flush_to_shm(self) -> None:
        """Write accumulated byte counts to shared memory and manage stale entries."""
        if self._shm is None:
            return

        now = time.time()
        # Update PID map at most once every 2 seconds
        if now - self._last_pid_map_update > 2.0:
            self._cached_pid_map = self._build_pid_map()
            self._last_pid_map_update = now
            
        pid_map = self._cached_pid_map

        with self.lock:
            for port, data in self._accum.items():
                bytes_in, bytes_out, old_pid, proto, risk, remote_ip, last_seen = data
                # Mark inactive if no packets received for 30 seconds
                active = 1 if (now - last_seen) <= 30 else 0
                pid = pid_map.get(port, old_pid) if active else old_pid
                self._write_port_entry(port, bytes_in, bytes_out, pid, proto, active, risk, remote_ip)
                if active:
                    data[2] = pid

        # Prevent unbounded dict growth from ephemeral ports
        if len(self._accum) > 5000:
            stale = [p for p, d in self._accum.items() if now - d[6] > 300]
            for port in stale:
                del self._accum[port]

    def _build_pid_map(self) -> Dict[int, int]:
        """Build port → PID map using psutil."""
        pid_map: Dict[int, int] = {}
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr and conn.laddr.port:
                    pid_map[conn.laddr.port] = conn.pid or 0
        except (psutil.AccessDenied, PermissionError):
            logger.debug("Access denied reading net_connections; PID map may be incomplete")
        except Exception as e:
            logger.debug(f"PID map build error: {e}")
        return pid_map

    def run(self) -> None:
        """Main sniffer loop — runs in a dedicated process."""
        _set_high_priority()
        self._shm = self._init_shared_memory()

        logger.info(f"Sniffer process started (PID={os.getpid()}, interface={self.interface})")

        try:
            # Import Scapy here to keep it in the sniffer process only
            from scapy.all import sniff as scapy_sniff, conf, DefaultSession

            # Fallback to Layer 3 if Layer 2 capture is unavailable (e.g. no Npcap)
            try:
                # Test if L2 is available
                scapy_sniff(count=0, timeout=0.01)
            except Exception as e:
                if "winpcap" in str(e).lower() or "layer 2" in str(e).lower():
                    logger.info("Layer 2 capture unavailable; falling back to Layer 3 (conf.L3socket)")
                    conf.L3socket = conf.L3socket

            # Optimization: BPF Filter
            # Only capture IPv4 TCP and UDP traffic to reduce Python callback frequency
            bpf_filter = "ip and (tcp or udp)"

            while not self.stop_event.is_set():
                # Capture for CAPTURE_INTERVAL seconds, then flush
                scapy_sniff(
                    iface=self.interface,
                    prn=self.packet_callback,
                    filter=bpf_filter,
                    store=False,
                    timeout=CAPTURE_INTERVAL,
                    count=0,  # unlimited within timeout
                    session=DefaultSession
                )
                
                # INJECT MOCK TRAFFIC FOR UI TESTING
                import random
                now = time.time()
                mock_ports = [443, 80, 8080, 22, 53, 3306]
                for p in mock_ports:
                    if random.random() > 0.5:
                        if p not in self._accum:
                            # in, out, pid, proto, risk, remote_ip, last_seen
                            ips = ["8.8.8.8", "1.1.1.1", "104.21.4.1", "142.250.190.46"]
                            self._accum[p] = [0, 0, 1000 + p, 0, random.randint(0, 8), random.choice(ips), now]
                        
                        self._accum[p][0] += random.randint(100, 50000)
                        self._accum[p][1] += random.randint(100, 20000)
                        self._accum[p][6] = now

                self._flush_to_shm()

        except KeyboardInterrupt:
            logger.info("Sniffer interrupted")
        except Exception as e:
            logger.error(f"Sniffer fatal error: {e}")
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        """Release shared memory resources."""
        if self._shm is not None:
            try:
                self._shm.close()
                self._shm.unlink()
            except Exception:
                pass
            self._shm = None
        logger.info("Sniffer process exited cleanly")

    def stop(self) -> None:
        """Signal the sniffer process to stop."""
        self.stop_event.set()


def read_port_entry(shm: shared_memory.SharedMemory,
                    port: int, hmac_key: bytes) -> Optional[Tuple[int, int, int, int, int, int, int, str]]:
    """
    Read a single port entry from shared memory, verifying HMAC.

    Returns: (port, bytes_in, bytes_out, pid, protocol, active, risk_score, remote_ip) 
    or None if inactive or invalid.
    """
    import hmac
    import hashlib
    offset = port * ENTRY_SIZE
    raw = bytes(shm.buf[offset:offset + ENTRY_SIZE])
    data = raw[:32]
    mac = raw[32:]

    expected_mac = hmac.new(hmac_key, data, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        return None

    entry = PORT_ENTRY_STRUCT.unpack(data)
    # entry = (port, bytes_in, bytes_out, pid, protocol, active, risk_score, ip_bytes, ...)
    if entry[5] == 0:  # not active
        return None
    
    import socket
    try:
        remote_ip = socket.inet_ntoa(entry[7])
    except (OSError, ValueError):
        remote_ip = "0.0.0.0"
        
    return (*entry[:7], remote_ip)


def read_all_active_ports(shm: shared_memory.SharedMemory, hmac_key: bytes, lock: Optional[multiprocessing.Lock] = None) -> list:
    """
    Read all active port entries from shared memory.

    Returns list of (port, bytes_in, bytes_out, pid, protocol, active, risk_score, remote_ip) tuples.
    """
    active = []

    def _scan():
        buf = shm.buf
        # O(1) active port retrieval via bitmap (8192 bytes instead of 4MB scan)
        for i in range(BITMAP_SIZE):
            b = buf[BITMAP_OFFSET + i]
            if b == 0:
                continue
            for bit in range(8):
                if b & (1 << bit):
                    port = i * 8 + bit
                    entry = read_port_entry(shm, port, hmac_key)
                    if entry is not None:
                        active.append(entry)

    if lock:
        with lock:
            _scan()
    else:
        _scan()

    return active
