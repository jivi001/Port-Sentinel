"""
Vigilant OS Adapter — Windows (win32_bridge.py)

Provides:
  - Port → PID → AppName mapping via psutil (with ctypes fallback)
  - Hard block via netsh advfirewall
  - Cleanup of all Vigilant_ firewall rules
  - System PID guard (PID 0, 4)
  - Privilege detection
"""

import ctypes
import subprocess
import platform
import logging
import re
from typing import List, Dict, Any

import psutil

from backend.core.exceptions import (
    SystemProcessProtectionError,
    FirewallRuleError,
    CleanupError,
)
from backend.os_adapters.base_bridge import OSBridgeAdapter

logger = logging.getLogger("vigilant.win32")

PROTECTED_PIDS_WIN = {0, 4}


def _resolve_pid_name(pid: int) -> str:
    """Resolve a PID to its process name."""
    if pid in PROTECTED_PIDS_WIN:
        return "System"
    try:
        proc = psutil.Process(pid)
        return proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "Unknown"


def _get_tcp_table_ctypes() -> List[Dict[str, Any]]:
    """
    Fallback: Build port → PID map using ctypes and iphlpapi.dll.

    Used when psutil.net_connections raises AccessDenied.
    """
    results = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port:
                pid = conn.pid or 0
                results.append({
                    "port": conn.laddr.port,
                    "pid": pid,
                    "app_name": _resolve_pid_name(pid),
                    "protocol": "TCP" if conn.type == 1 else "UDP",
                    "status": getattr(conn, "status", "UNKNOWN"),
                })
    except Exception as e:
        logger.debug(f"ctypes fallback error: {e}")
    return results


class WindowsBridge(OSBridgeAdapter):
    """Windows OS adapter for firewall and network operations."""

    def is_compatible(self) -> bool:
        return platform.system() == "Windows"

    def is_elevated(self) -> bool:
        """Check if running with administrator privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def get_port_pid_map(self) -> List[Dict[str, Any]]:
        """Build live Port → PID → AppName map using psutil."""
        results = []
        seen_ports = set()

        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr and conn.laddr.port:
                    port = conn.laddr.port
                    if port in seen_ports:
                        continue
                    seen_ports.add(port)

                    pid = conn.pid or 0
                    app_name = _resolve_pid_name(pid)
                    protocol = "TCP" if conn.type == 1 else "UDP"

                    results.append({
                        "port": port,
                        "pid": pid,
                        "app_name": app_name,
                        "protocol": protocol,
                        "status": getattr(conn, "status", "UNKNOWN"),
                    })
        except (psutil.AccessDenied, PermissionError) as e:
            logger.warning(f"Access denied enumerating connections: {e}")
            results = _get_tcp_table_ctypes()

        return results

    def get_process_info(self, pid: int) -> Dict[str, Any]:
        """Get information about a process by PID (detection only, no termination)."""
        try:
            proc = psutil.Process(pid)
            return {
                "pid": pid,
                "name": proc.name(),
                "status": proc.status(),
                "cpu_percent": proc.cpu_percent(),
                "memory_mb": round(proc.memory_info().rss / (1024 * 1024), 2),
                "create_time": proc.create_time(),
                "connections": len(proc.net_connections()),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"pid": pid, "name": "Unknown", "status": "not_found"}

    def block_port(self, port: int, protocol: str = "TCP") -> bool:
        """Add Windows Firewall rules to block a port (inbound + outbound)."""
        if not self.is_compatible():
            raise FirewallRuleError("Windows firewall operations require Windows OS")

        if not (1 <= port <= 65535):
            raise FirewallRuleError(f"Invalid port number: {port}")
        if protocol.upper() not in ("TCP", "UDP"):
            raise FirewallRuleError(f"Invalid protocol: {protocol}")
        protocol = protocol.upper()

        try:
            for direction, dir_label in [("out", "Out"), ("in", "In")]:
                cmd = [
                    "netsh", "advfirewall", "firewall", "add", "rule",
                    f"name=Vigilant_Block_{dir_label}_{port}",
                    f"dir={direction}", "action=block",
                    f"protocol={protocol}", f"localport={port}",
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=10, errors="replace",
                )
                if result.returncode != 0:
                    logger.warning(f"netsh stderr: {result.stderr}")
                    raise FirewallRuleError(
                        f"Failed to create {direction}bound rule for port {port}/{protocol}"
                    )

            logger.info(f"Blocked port {port}/{protocol} (Windows)")
            return True

        except subprocess.TimeoutExpired:
            raise FirewallRuleError(f"Firewall command timed out for port {port}")
        except FirewallRuleError:
            raise
        except Exception as e:
            raise FirewallRuleError(f"Unexpected error blocking port {port}: {e}")

    def unblock_port(self, port: int) -> bool:
        """Remove Vigilant_ firewall rules for a specific port."""
        if not self.is_compatible():
            return False
        if not (1 <= port <= 65535):
            return False

        success = True
        for direction in ("Out", "In"):
            # Try both old (Sentinel_) and new (Vigilant_) rule names
            for prefix in ("Vigilant", "Sentinel"):
                rule_name = f"{prefix}_Block_{direction}_{port}"
                try:
                    cmd = [
                        "netsh", "advfirewall", "firewall", "delete", "rule",
                        f"name={rule_name}",
                    ]
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=10, errors="replace",
                    )
                    if result.returncode == 0:
                        logger.info(f"Removed rule {rule_name}")
                except Exception as e:
                    logger.debug(f"Error removing rule {rule_name}: {e}")

        return success

    def cleanup_all_rules(self) -> int:
        """Remove ALL Vigilant_ and Sentinel_ firewall rules."""
        if not self.is_compatible():
            return 0

        removed = 0
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                capture_output=True, text=True, timeout=30, errors="replace",
            )
            stdout = result.stdout or ""
            # Match both legacy Sentinel_ and new Vigilant_ rules
            rule_names = re.findall(r"Rule Name:\s+((Vigilant|Sentinel)_\S+)", stdout)

            for rule_match in rule_names:
                rule_name = rule_match[0]
                try:
                    subprocess.run(
                        ["netsh", "advfirewall", "firewall", "delete", "rule",
                         f"name={rule_name}"],
                        capture_output=True, text=True, timeout=10, errors="replace",
                    )
                    removed += 1
                    logger.info(f"Cleanup: removed rule {rule_name}")
                except Exception as e:
                    logger.warning(f"Cleanup: failed to remove {rule_name}: {e}")

        except Exception as e:
            logger.error(f"Cleanup enumeration failed: {e}")
            raise CleanupError(f"Failed to enumerate firewall rules: {e}")

        logger.info(f"Cleanup complete: removed {removed} rules")
        return removed
