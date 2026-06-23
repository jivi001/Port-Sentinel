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
from typing import List, Dict, Optional, Tuple, Any

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

from backend.os_adapters.base_bridge import OSBridgeAdapter

class WindowsBridge(OSBridgeAdapter):
    def is_compatible(self) -> bool:
        return platform.system() == "Windows"

    def get_port_pid_map(self) -> List[Dict[str, Any]]:
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

    def block_port(self, port: int, protocol: str = "TCP") -> bool:
        """
        Hard Block: Add Windows Firewall rules to block a port.

        Creates two rules (inbound + outbound) prefixed with "Sentinel_".
        """
        if not self.is_compatible():
            raise FirewallRuleError("Windows firewall operations require Windows OS")
            
        if not (1 <= port <= 65535):
            raise FirewallRuleError(f"Invalid port number: {port}. Must be 1-65535.")
        if protocol.upper() not in ('TCP', 'UDP'):
            raise FirewallRuleError(f"Invalid protocol: {protocol}. Must be TCP or UDP.")
        protocol = protocol.upper()

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
                logger.warning(f"netsh stderr: {result_out.stderr}")
                raise FirewallRuleError(f"Failed to create outbound firewall rule for port {port}/{protocol}")

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
                logger.warning(f"netsh stderr: {result_in.stderr}")
                raise FirewallRuleError(f"Failed to create inbound firewall rule for port {port}/{protocol}")

            logger.info(f"Hard blocked port {port}/{protocol} (Windows)")
            return True

        except subprocess.TimeoutExpired:
            raise FirewallRuleError(f"Firewall command timed out for port {port}")
        except FirewallRuleError:
            raise
        except Exception as e:
            raise FirewallRuleError(f"Unexpected error blocking port {port}: {e}")

    def unblock_port(self, port: int) -> bool:
        """Remove Sentinel_ firewall rules for a specific port."""
        if not self.is_compatible():
            return False
            
        if not (1 <= port <= 65535):
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

    def cleanup_all_rules(self) -> int:
        """
        Remove ALL firewall rules prefixed with 'Sentinel_'.

        Returns the number of rules removed.
        Called on exit via atexit hook.
        """
        if not self.is_compatible():
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
