"""
Vigilant OS Adapter — macOS / Darwin (darwin_bridge.py)

Provides:
  - Port → PID → AppName mapping via lsof / psutil
  - Hard block via pfctl (Packet Filter)
  - Cleanup of all Vigilant pf rules
  - System PID guard (PID 0 = kernel_task, PID 1 = launchd)
  - Privilege detection
"""

import os
import subprocess
import platform
import logging
import re
import tempfile
from typing import List, Dict, Optional, Any

import psutil

from backend.core.exceptions import (
    FirewallRuleError,
    CleanupError,
)
from backend.os_adapters.base_bridge import OSBridgeAdapter

logger = logging.getLogger("vigilant.darwin")

PROTECTED_PIDS_MAC = {0, 1}
PF_ANCHOR = "com.vigilant"
PF_RULES_FILE = os.path.join(tempfile.gettempdir(), "vigilant_pf_rules.conf")

# Module-level state for active PF rules
_active_rules: Dict[int, str] = {}


def _resolve_pid_name(pid: int) -> str:
    """Resolve a PID to its process name."""
    if pid in PROTECTED_PIDS_MAC:
        return "System"
    try:
        proc = psutil.Process(pid)
        return proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "Unknown"


def _get_ports_psutil(seen_ports: set) -> List[Dict[str, Any]]:
    """Fallback: get port map via psutil."""
    results = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port:
                port = conn.laddr.port
                if port in seen_ports:
                    continue
                seen_ports.add(port)
                pid = conn.pid or 0
                results.append({
                    "port": port,
                    "pid": pid,
                    "app_name": _resolve_pid_name(pid),
                    "protocol": "TCP" if conn.type == 1 else "UDP",
                    "status": getattr(conn, "status", "UNKNOWN"),
                })
    except (psutil.AccessDenied, PermissionError):
        logger.debug("psutil access denied on macOS")
    return results


def _parse_lsof_output(stdout: str, seen_ports: set) -> List[Dict[str, Any]]:
    """Parse lsof -F pcn output into port entries."""
    results = []
    current_pid = 0
    current_name = "Unknown"

    for line in stdout.strip().split("\n"):
        if not line:
            continue
        if line.startswith("p"):
            try:
                current_pid = int(line[1:])
            except ValueError:
                current_pid = 0
        elif line.startswith("c"):
            current_name = line[1:]
        elif line.startswith("n"):
            # Parse network address: e.g., "n*:443" or "n127.0.0.1:8080"
            addr = line[1:]
            if ":" in addr:
                try:
                    port_str = addr.rsplit(":", 1)[1]
                    port = int(port_str)
                    if port not in seen_ports:
                        seen_ports.add(port)
                        results.append({
                            "port": port,
                            "pid": current_pid,
                            "app_name": current_name,
                            "protocol": "TCP",
                            "status": "ESTABLISHED",
                        })
                except (ValueError, IndexError):
                    pass

    return results


def _write_pf_rules():
    """Write all active rules to the PF rules file."""
    try:
        with open(PF_RULES_FILE, "w", encoding="utf-8") as f:
            for rule in _active_rules.values():
                f.write(rule + "\n")
    except Exception as e:
        logger.error(f"Failed to write PF rules file: {e}")


def _reload_pf():
    """Reload PF rules from the rules file."""
    try:
        subprocess.run(
            ["sudo", "pfctl", "-a", PF_ANCHOR, "-f", PF_RULES_FILE],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        logger.error(f"Failed to reload PF rules: {e}")


class DarwinBridge(OSBridgeAdapter):
    """macOS OS adapter for firewall and network operations."""

    def is_compatible(self) -> bool:
        return platform.system() == "Darwin"

    def is_elevated(self) -> bool:
        """Check if running with root privileges."""
        return hasattr(os, "geteuid") and os.geteuid() == 0

    def get_port_pid_map(self) -> List[Dict[str, Any]]:
        """Build live Port → PID → AppName map using lsof, with psutil fallback."""
        results = []
        seen_ports = set()

        try:
            cmd = ["lsof", "-iTCP", "-iUDP", "-n", "-P", "-F", "pcn"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                results = _parse_lsof_output(result.stdout, seen_ports)
            else:
                results = _get_ports_psutil(seen_ports)
        except FileNotFoundError:
            results = _get_ports_psutil(seen_ports)
        except subprocess.TimeoutExpired:
            results = _get_ports_psutil(seen_ports)

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

    def block_port(self, port: int, protocol: str = "tcp", interface: str = "en0") -> bool:
        """Add a pf rule to block traffic on a port."""
        if not self.is_compatible():
            raise FirewallRuleError("pfctl requires macOS")
        if not (1 <= port <= 65535):
            raise FirewallRuleError(f"Invalid port: {port}")
        if protocol.lower() not in ("tcp", "udp"):
            raise FirewallRuleError(f"Invalid protocol: {protocol}")
        if not re.match(r"^[a-zA-Z0-9]+$", interface):
            raise FirewallRuleError(f"Invalid interface: {interface}")

        rule = f"block drop on {interface} proto {protocol.lower()} from any to any port {port}"

        try:
            _active_rules[port] = rule
            _write_pf_rules()

            result = subprocess.run(
                ["sudo", "pfctl", "-a", PF_ANCHOR, "-f", PF_RULES_FILE],
                capture_output=True, text=True, timeout=10,
            )
            subprocess.run(
                ["sudo", "pfctl", "-e"],
                capture_output=True, text=True, timeout=10,
            )

            logger.info(f"Blocked port {port}/{protocol} on {interface} (macOS)")
            return True

        except subprocess.TimeoutExpired:
            raise FirewallRuleError(f"pfctl timed out for port {port}")
        except Exception as e:
            raise FirewallRuleError(f"Error blocking port {port}: {e}")

    def unblock_port(self, port: int) -> bool:
        """Remove the pf rule for a specific port."""
        if port not in _active_rules and os.path.exists(PF_RULES_FILE):
            try:
                with open(PF_RULES_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        match = re.search(r"port\s+(\d+)\s*$", line.strip())
                        if match:
                            parsed_port = int(match.group(1))
                            _active_rules[parsed_port] = line.strip()
            except Exception as e:
                logger.debug(f"Could not load PF rules from file: {e}")

        if port in _active_rules:
            del _active_rules[port]
            _write_pf_rules()
            _reload_pf()
            logger.info(f"Unblocked port {port} (macOS)")
            return True
        logger.info(f"Port {port} already unblocked (macOS)")
        return True

    def cleanup_all_rules(self) -> int:
        """Remove ALL Vigilant pf rules and flush the anchor."""
        removed = len(_active_rules)
        _active_rules.clear()

        try:
            subprocess.run(
                ["sudo", "pfctl", "-a", PF_ANCHOR, "-Fr"],
                capture_output=True, text=True, timeout=10,
            )
            if os.path.exists(PF_RULES_FILE):
                os.remove(PF_RULES_FILE)
            logger.info(f"Cleanup complete: removed {removed} pf rules")
        except Exception as e:
            logger.error(f"PF cleanup error: {e}")
            raise CleanupError(f"Failed to clean up pf rules: {e}")

        return removed
