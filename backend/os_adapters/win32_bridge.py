"""
Sentinel OS Adapter — Windows (win32_bridge.py)

Provides:
  - Port → PID → AppName mapping via ctypes → iphlpapi.dll
  - Process suspend/resume/kill via psutil
  - Hard block via netsh advfirewall
  - Cleanup of all Sentinel_ firewall rules
  - System PID guard (PID 4 = System)
"""

import ctypes
import ctypes.wintypes
import subprocess
import platform
import logging
import re
from typing import List, Dict, Optional, Tuple

import psutil

from backend.core.exceptions import (
    SystemProcessProtectionError,
    FirewallRuleError,
    CleanupError,
)

logger = logging.getLogger("sentinel.win32")

# --- System PID protection ---
PROTECTED_PIDS_WIN = {0, 4}  # PID 0 = Idle, PID 4 = System


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def _check_system_pid(pid: int, operation: str) -> None:
    """Raise SystemProcessProtectionError for protected PIDs."""
    if pid in PROTECTED_PIDS_WIN:
        raise SystemProcessProtectionError(pid, operation)


# --- Port → PID → AppName Mapping ---

def get_port_pid_map() -> List[Dict[str, any]]:
    """
    Build live Port → PID → AppName map using psutil.

    Falls back to ctypes iphlpapi.dll if psutil is insufficient.
    Returns list of dicts with keys: port, pid, app_name, protocol, status
    """
    results = []
    seen_ports = set()

    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr and conn.laddr.port:
                port = conn.laddr.port
                if port in seen_ports:
                    continue
                seen_ports.add(port)

                pid = conn.pid or 0
                app_name = _resolve_pid_name(pid)
                protocol = "TCP" if conn.type == 1 else "UDP"  # SOCK_STREAM=1, SOCK_DGRAM=2

                results.append({
                    "port": port,
                    "pid": pid,
                    "app_name": app_name,
                    "protocol": protocol,
                    "status": conn.status if hasattr(conn, 'status') else "UNKNOWN",
                })
    except (psutil.AccessDenied, PermissionError) as e:
        logger.warning(f"Access denied enumerating connections: {e}")
        # Fallback: use iphlpapi via ctypes
        results = _get_tcp_table_ctypes()

    return results


def _resolve_pid_name(pid: int) -> str:
    """Resolve PID to application name."""
    if pid in PROTECTED_PIDS_WIN:
        return "System"
    try:
        proc = psutil.Process(pid)
        return proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "Unknown"


def _get_tcp_table_ctypes() -> List[Dict[str, any]]:
    """
    Enumerate TCP connections via ctypes → iphlpapi.dll.

    Uses GetExtendedTcpTable to get PID information.
    """
    if not is_windows():
        return []

    results = []
    try:
        iphlpapi = ctypes.windll.iphlpapi

        # MIB_TCP_TABLE_OWNER_PID = 5
        TCP_TABLE_OWNER_PID_ALL = 5
        AF_INET = 2

        # First call to get required buffer size
        buf_size = ctypes.wintypes.DWORD(0)
        iphlpapi.GetExtendedTcpTable(None, ctypes.byref(buf_size), False,
                                      AF_INET, TCP_TABLE_OWNER_PID_ALL, 0)

        buf = ctypes.create_string_buffer(buf_size.value)
        ret = iphlpapi.GetExtendedTcpTable(buf, ctypes.byref(buf_size), False,
                                            AF_INET, TCP_TABLE_OWNER_PID_ALL, 0)

        if ret != 0:
            logger.warning(f"GetExtendedTcpTable returned {ret}")
            return results

        # Parse the table manually
        # First 4 bytes = number of entries
        num_entries = int.from_bytes(buf.raw[0:4], byteorder='little')

        # Each entry: state(4) + localAddr(4) + localPort(4) + remoteAddr(4) + remotePort(4) + pid(4) = 24 bytes
        ENTRY_OFFSET = 4  # skip dwNumEntries
        ENTRY_LENGTH = 24

        for i in range(min(num_entries, 10000)):  # safety cap
            offset = ENTRY_OFFSET + (i * ENTRY_LENGTH)
            if offset + ENTRY_LENGTH > len(buf.raw):
                break

            entry = buf.raw[offset:offset + ENTRY_LENGTH]
            local_port = int.from_bytes(entry[8:12], byteorder='big') & 0xFFFF
            pid = int.from_bytes(entry[20:24], byteorder='little')

            results.append({
                "port": local_port,
                "pid": pid,
                "app_name": _resolve_pid_name(pid),
                "protocol": "TCP",
                "status": "ESTABLISHED",
            })

    except Exception as e:
        logger.error(f"ctypes TCP table enumeration failed: {e}")

    return results


# --- Control Operations ---

def suspend_process(pid: int) -> bool:
    """Soft Block: Suspend a process (freeze network without data loss)."""
    _check_system_pid(pid, "suspend")
    try:
        proc = psutil.Process(pid)
        proc.suspend()
        logger.info(f"Suspended process PID={pid} ({proc.name()})")
        return True
    except psutil.NoSuchProcess:
        logger.warning(f"Process PID={pid} not found")
        return False
    except psutil.AccessDenied:
        logger.error(f"Access denied suspending PID={pid}")
        return False


def resume_process(pid: int) -> bool:
    """Resume a previously suspended process."""
    _check_system_pid(pid, "resume")
    try:
        proc = psutil.Process(pid)
        proc.resume()
        logger.info(f"Resumed process PID={pid} ({proc.name()})")
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        logger.error(f"Resume failed for PID={pid}: {e}")
        return False


def kill_process(pid: int) -> bool:
    """Kill a process."""
    _check_system_pid(pid, "kill")
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill()
        try:
            proc.wait(timeout=3)
        except psutil.TimeoutExpired:
            logger.warning(f"Kill timed out waiting for PID={pid} ({name}) to exit")
            return not proc.is_running()
        logger.info(f"Killed process PID={pid} ({name})")
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        logger.error(f"Kill failed for PID={pid}: {e}")
        return False


# --- Firewall — Hard Block ---

def block_port(port: int, protocol: str = "TCP") -> bool:
    """
    Hard Block: Add Windows Firewall rules to block a port.

    Creates two rules (inbound + outbound) prefixed with "Sentinel_".
    """
    if not is_windows():
        raise FirewallRuleError("Windows firewall operations require Windows OS")

    try:
        # Outbound rule
        cmd_out = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name=Sentinel_Block_Out_{port}",
            "dir=out", "action=block",
            f"protocol={protocol}",
            f"localport={port}",
        ]
        result_out = subprocess.run(cmd_out, capture_output=True, text=True, timeout=10, errors='replace')
        if result_out.returncode != 0:
            raise FirewallRuleError(f"Outbound rule failed: {result_out.stderr}")

        # Inbound rule
        cmd_in = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name=Sentinel_Block_In_{port}",
            "dir=in", "action=block",
            f"protocol={protocol}",
            f"localport={port}",
        ]
        result_in = subprocess.run(cmd_in, capture_output=True, text=True, timeout=10, errors='replace')
        if result_in.returncode != 0:
            raise FirewallRuleError(f"Inbound rule failed: {result_in.stderr}")

        logger.info(f"Hard blocked port {port}/{protocol} (Windows)")
        return True

    except subprocess.TimeoutExpired:
        raise FirewallRuleError(f"Firewall command timed out for port {port}")
    except FirewallRuleError:
        raise
    except Exception as e:
        raise FirewallRuleError(f"Unexpected error blocking port {port}: {e}")


def unblock_port(port: int) -> bool:
    """Remove Sentinel_ firewall rules for a specific port."""
    if not is_windows():
        return False

    def _rule_missing(stdout: str, stderr: str) -> bool:
        text = f"{stdout}\n{stderr}".lower()
        return "no rules match" in text

    success = True
    for direction in ["Out", "In"]:
        rule_name = f"Sentinel_Block_{direction}_{port}"
        try:
            cmd = [
                "netsh", "advfirewall", "firewall", "delete", "rule",
                f"name={rule_name}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, errors='replace')
            if result.returncode != 0:
                if _rule_missing(result.stdout or "", result.stderr or ""):
                    logger.info(f"Rule {rule_name} already absent; continuing")
                else:
                    logger.warning(f"Failed to remove rule {rule_name}: {result.stderr}")
                    success = False
        except Exception as e:
            logger.warning(f"Error removing rule {rule_name}: {e}")
            success = False

    return success


def cleanup_all_rules() -> int:
    """
    Remove ALL firewall rules prefixed with 'Sentinel_'.

    Returns the number of rules removed.
    Called on exit via atexit hook.
    """
    if not is_windows():
        return 0

    removed = 0
    try:
        # List all rules
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            capture_output=True, text=True, timeout=30, errors='replace'
        )

        stdout = result.stdout or ""
        # Find all Sentinel_ rules
        rule_names = re.findall(r'Rule Name:\s+(Sentinel_\S+)', stdout)

        for rule_name in rule_names:
            try:
                subprocess.run(
                    ["netsh", "advfirewall", "firewall", "delete", "rule",
                     f"name={rule_name}"],
                    capture_output=True, text=True, timeout=10, errors='replace'
                )
                removed += 1
                logger.info(f"Cleanup: removed rule {rule_name}")
            except Exception as e:
                logger.warning(f"Cleanup: failed to remove {rule_name}: {e}")

    except Exception as e:
        logger.error(f"Cleanup enumeration failed: {e}")
        raise CleanupError(f"Failed to enumerate firewall rules: {e}")

    logger.info(f"Cleanup complete: removed {removed} Sentinel_ rules")
    return removed
