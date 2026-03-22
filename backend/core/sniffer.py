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
ENTRY_SIZE = 32  # bytes per port entry
SHM_SIZE = MAX_PORTS * ENTRY_SIZE
SHM_NAME = "sentinel_traffic_shm"
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

    def __init__(self, interface: Optional[str] = None, 
                 stop_event: Optional[multiprocessing.Event] = None,
                 lock: Optional[multiprocessing.Lock] = None):
        super().__init__(daemon=True)
        self.interface = interface
        self.stop_event = stop_event or multiprocessing.Event()
        self.lock = lock or multiprocessing.Lock()
        self._shm: Optional[shared_memory.SharedMemory] = None
        # Local accumulation buffer: port -> (bytes_in, bytes_out, pid, proto)
        self._accum: Dict[int, list] = {}

    def _init_shared_memory(self) -> shared_memory.SharedMemory:
        """Create or attach to the shared memory segment."""
        try:
            shm = shared_memory.SharedMemory(name=SHM_NAME, create=True, size=SHM_SIZE)
            # Zero-initialize
            shm.buf[:SHM_SIZE] = b'\x00' * SHM_SIZE
            logger.info(f"Created shared memory '{SHM_NAME}' ({SHM_SIZE} bytes)")
        except FileExistsError:
            shm = shared_memory.SharedMemory(name=SHM_NAME, create=False, size=SHM_SIZE)
            logger.info(f"Attached to existing shared memory '{SHM_NAME}'")
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
        try:
            ip_bytes = socket.inet_aton(remote_ip)
        except:
            ip_bytes = b'\x00\x00\x00\x00'

        # Guard against overflow
        bytes_in = bytes_in % (2**64)
        bytes_out = bytes_out % (2**64)
        
        data = PORT_ENTRY_STRUCT.pack(port, bytes_in, bytes_out, pid, protocol, active, risk_score, ip_bytes)
        self._shm.buf[offset:offset + ENTRY_SIZE] = data

    def packet_callback(self, packet) -> None:
        """
        Callback invoked by Scapy for each captured packet.
        """
        try:
            # Lazy import
            from scapy.layers.inet import IP, TCP, UDP
            from backend.core.threat_intel import threat_manager

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
                risk = threat_manager.get_risk_score(remote_ip)
                if sport not in self._accum:
                    self._accum[sport] = [0, 0, 0, protocol, 0, "0.0.0.0"] # in, out, pid, proto, risk, remote_ip
                self._accum[sport][1] += payload_len
                self._accum[sport][4] = max(self._accum[sport][4], risk)
                self._accum[sport][5] = remote_ip

            # Accumulate for destination port (inbound)
            if dport > 0 and dport < MAX_PORTS:
                remote_ip = ip_layer.src
                risk = threat_manager.get_risk_score(remote_ip)
                if dport not in self._accum:
                    self._accum[dport] = [0, 0, 0, protocol, 0, "0.0.0.0"]
                self._accum[dport][0] += payload_len
                self._accum[dport][4] = max(self._accum[dport][4], risk)
                self._accum[dport][5] = remote_ip

        except Exception as e:
            logger.debug(f"Packet callback error: {e}")

    def _flush_to_shm(self) -> None:
        """Write accumulated byte counts to shared memory."""
        if self._shm is None:
            return

        pid_map = self._build_pid_map()

        with self.lock:
            for port, (bytes_in, bytes_out, old_pid, proto, risk, remote_ip) in self._accum.items():
                pid = pid_map.get(port, old_pid)
                self._write_port_entry(port, bytes_in, bytes_out, pid, proto, 1, risk, remote_ip)
                self._accum[port][2] = pid 

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
                    port: int) -> Optional[Tuple[int, int, int, int, int, int, int, str]]:
    """
    Read a single port entry from shared memory.

    Returns: (port, bytes_in, bytes_out, pid, protocol, active, risk_score, remote_ip) 
    or None if inactive.
    """
    offset = port * ENTRY_SIZE
    data = bytes(shm.buf[offset:offset + ENTRY_SIZE])
    entry = PORT_ENTRY_STRUCT.unpack(data)
    # entry = (port, bytes_in, bytes_out, pid, protocol, active, risk_score, ip_bytes, ...)
    if entry[5] == 0:  # not active
        return None
    
    import socket
    try:
        remote_ip = socket.inet_ntoa(entry[7])
    except:
        remote_ip = "0.0.0.0"
        
    return (*entry[:7], remote_ip)


def read_all_active_ports(shm: shared_memory.SharedMemory, lock: Optional[multiprocessing.Lock] = None) -> list:
    """
    Read all active port entries from shared memory.

    Returns list of (port, bytes_in, bytes_out, pid, protocol, active, risk_score) tuples.
    """
    active = []
    
    # Define the range to scan (can be optimized if we track active ports elsewhere)
    ports_to_check = range(MAX_PORTS)

    if lock:
        with lock:
            for port in ports_to_check:
                entry = read_port_entry(shm, port)
                if entry is not None:
                    active.append(entry)
    else:
        for port in ports_to_check:
            entry = read_port_entry(shm, port)
            if entry is not None:
                active.append(entry)
                
    return active
