"""
Vigilant OS Adapter — Linux (linux_bridge.py)

Provides:
  - Port → PID → AppName mapping via psutil
  - Hard block via iptables (with nftables fallback detection)
  - Cleanup of all Vigilant_ iptables rules
  - System PID guard (PID 0, 1, 2)
  - Privilege detection
"""

import os
import subprocess
import platform
import logging
import shutil
from typing import List, Dict, Any

import psutil

from backend.core.exceptions import (
    FirewallRuleError,
    CleanupError,
)
from backend.os_adapters.base_bridge import OSBridgeAdapter

logger = logging.getLogger("vigilant.linux")

PROTECTED_PIDS_LINUX = {0, 1, 2}


def _resolve_pid_name(pid: int) -> str:
    """Resolve a PID to its process name."""
    if pid in PROTECTED_PIDS_LINUX:
        return "System"
    try:
        proc = psutil.Process(pid)
        return proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "Unknown"


class LinuxBridge(OSBridgeAdapter):
    """Linux OS adapter for firewall and network operations."""

    def __init__(self):
        self._use_sudo = os.geteuid() != 0 if hasattr(os, "geteuid") else True
        self._firewall_cmd = self._detect_firewall()

    def _detect_firewall(self) -> str:
        """Detect available firewall command (iptables or nftables)."""
        if shutil.which("iptables"):
            return "iptables"
        if shutil.which("nft"):
            return "nft"
        logger.warning("Neither iptables nor nft found — firewall operations unavailable")
        return "iptables"  # Default, will fail gracefully

    def _fw_cmd(self, args: list) -> list:
        """Prepend sudo if not running as root."""
        cmd = [self._firewall_cmd] + args
        if self._use_sudo:
            cmd = ["sudo"] + cmd
        return cmd

    def is_compatible(self) -> bool:
        return platform.system() == "Linux"

    def is_elevated(self) -> bool:
        """Check if running with root privileges."""
        return hasattr(os, "geteuid") and os.geteuid() == 0

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
            logger.warning(f"psutil access denied: {e}")

        return results

    def get_process_info(self, pid: int) -> Dict[str, Any]:
        """Get information about a process (detection only)."""
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

    def block_port(self, port: int, protocol: str = "tcp") -> bool:
        """Add iptables rule to block traffic on a port."""
        if not self.is_compatible():
            raise FirewallRuleError("iptables operations require Linux")
        if not (1 <= port <= 65535):
            raise FirewallRuleError(f"Invalid port: {port}")
        if protocol.lower() not in ("tcp", "udp"):
            raise FirewallRuleError(f"Invalid protocol: {protocol}")

        protocol = protocol.lower()
        comment = f"Vigilant_Block_{port}_{protocol}"

        try:
            # Check if rule already exists
            check_cmd = self._fw_cmd([
                "-C", "INPUT", "-p", protocol, "--dport", str(port),
                "-j", "DROP", "-m", "comment", "--comment", comment,
            ])
            res = subprocess.run(check_cmd, capture_output=True)
            if res.returncode == 0:
                logger.info(f"Port {port}/{protocol} already blocked")
                return True

            # Insert rule at top of INPUT chain
            cmd = self._fw_cmd([
                "-I", "INPUT", "1", "-p", protocol, "--dport", str(port),
                "-j", "DROP", "-m", "comment", "--comment", comment,
            ])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise FirewallRuleError(f"iptables failed: {result.stderr.strip()}")

            logger.info(f"Blocked port {port}/{protocol} (Linux)")
            return True

        except subprocess.TimeoutExpired:
            raise FirewallRuleError(f"iptables timed out for port {port}")
        except FirewallRuleError:
            raise
        except Exception as e:
            raise FirewallRuleError(f"Error blocking port {port}: {e}")

    def unblock_port(self, port: int) -> bool:
        """Remove iptables rules for a specific port."""
        if not self.is_compatible():
            return False

        success = True
        for proto in ("tcp", "udp"):
            for prefix in ("Vigilant", "Sentinel"):
                comment = f"{prefix}_Block_{port}_{proto}"
                try:
                    cmd = self._fw_cmd([
                        "-D", "INPUT", "-p", proto, "--dport", str(port),
                        "-j", "DROP", "-m", "comment", "--comment", comment,
                    ])
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        logger.info(f"Removed rule {comment}")
                except Exception as e:
                    logger.debug(f"Error removing rule {comment}: {e}")

        return success

    def cleanup_all_rules(self) -> int:
        """Remove ALL Vigilant/Sentinel iptables rules."""
        if not self.is_compatible():
            return 0

        removed = 0
        try:
            cmd = self._fw_cmd(["-L", "INPUT", "-n", "--line-numbers"])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise CleanupError("Failed to list iptables rules")

            lines = result.stdout.strip().split("\n")
            to_delete = []
            for line in lines:
                if "Vigilant_Block_" in line or "Sentinel_Block_" in line:
                    parts = line.split()
                    if parts and parts[0].isdigit():
                        to_delete.append(int(parts[0]))

            # Delete from bottom to avoid line number shifting
            to_delete.sort(reverse=True)
            for line_num in to_delete:
                del_cmd = self._fw_cmd(["-D", "INPUT", str(line_num)])
                del_res = subprocess.run(del_cmd, capture_output=True, text=True, timeout=10)
                if del_res.returncode == 0:
                    removed += 1

            logger.info(f"Cleanup complete: removed {removed} rules")

        except CleanupError:
            raise
        except Exception as e:
            logger.error(f"iptables cleanup error: {e}")
            raise CleanupError(f"Failed to clean up iptables: {e}")

        return removed
