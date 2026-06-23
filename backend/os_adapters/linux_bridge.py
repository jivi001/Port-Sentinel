"""
Sentinel OS Adapter — Linux (linux_bridge.py)

Provides:
  - Port → PID → AppName mapping via ss / psutil
  - Hard block via iptables
  - Cleanup of all Sentinel_ iptables rules
  - System PID guard (PID 0, 1, 2)
"""

import subprocess
import platform
import logging
import tempfile
import os
import re
from typing import List, Dict, Optional, Any

import psutil

from backend.core.exceptions import (
    SystemProcessProtectionError,
    FirewallRuleError,
    CleanupError,
)

logger = logging.getLogger("sentinel.linux")

PROTECTED_PIDS_LINUX = {0, 1, 2}


from backend.os_adapters.base_bridge import OSBridgeAdapter

class LinuxBridge(OSBridgeAdapter):
    def is_compatible(self) -> bool:
        return platform.system() == "Linux"

    def get_port_pid_map(self) -> List[Dict[str, Any]]:
        """
        Build live Port → PID → AppName map using psutil.
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
                    protocol = "TCP" if conn.type == 1 else "UDP"

                    results.append({
                        "port": port,
                        "pid": pid,
                        "app_name": app_name,
                        "protocol": protocol,
                        "status": conn.status if hasattr(conn, 'status') else "UNKNOWN",
                    })
        except (psutil.AccessDenied, PermissionError) as e:
            logger.warning(f"psutil access denied: {e}")

        return results

    def block_port(self, port: int, protocol: str = "tcp") -> bool:
        """
        Hard Block: Add iptables rule to block traffic on a port.
        """
        if not self.is_compatible():
            raise FirewallRuleError("iptables operations require Linux")
            
        if not (1 <= port <= 65535):
            raise FirewallRuleError(f"Invalid port number: {port}. Must be 1-65535.")
        if protocol.lower() not in ('tcp', 'udp'):
            raise FirewallRuleError(f"Invalid protocol: {protocol}. Must be tcp or udp.")

        protocol = protocol.lower()
        comment = f"Sentinel_Block_{port}_{protocol}"

        try:
            # Check if rule exists
            check_cmd = ["sudo", "iptables", "-C", "INPUT", "-p", protocol, "--dport", str(port), "-j", "DROP", "-m", "comment", "--comment", comment]
            res = subprocess.run(check_cmd, capture_output=True)
            if res.returncode == 0:
                logger.info(f"Port {port}/{protocol} is already blocked.")
                return True

            # Insert rule at top of INPUT chain
            cmd = ["sudo", "iptables", "-I", "INPUT", "1", "-p", protocol, "--dport", str(port), "-j", "DROP", "-m", "comment", "--comment", comment]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                logger.warning(f"iptables stderr: {result.stderr.strip()}")
                raise FirewallRuleError(f"Failed to create firewall rule: {result.stderr}")

            logger.info(f"Hard blocked port {port}/{protocol} (Linux)")
            return True

        except subprocess.TimeoutExpired:
            raise FirewallRuleError(f"iptables timed out for port {port}")
        except Exception as e:
            raise FirewallRuleError(f"Error blocking port {port}: {e}")

    def unblock_port(self, port: int) -> bool:
        """Remove the iptables rule for a specific port."""
        if not self.is_compatible():
            return False

        success = True
        for proto in ["tcp", "udp"]:
            comment = f"Sentinel_Block_{port}_{proto}"
            try:
                # Delete rule based on exact specification
                cmd = ["sudo", "iptables", "-D", "INPUT", "-p", proto, "--dport", str(port), "-j", "DROP", "-m", "comment", "--comment", comment]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode != 0 and "Does a matching rule exist in that chain" not in result.stderr:
                    logger.warning(f"iptables stderr on delete: {result.stderr.strip()}")
                    success = False
            except Exception as e:
                logger.warning(f"Error removing iptables rule for {port}: {e}")
                success = False

        if success:
            logger.info(f"Unblocked port {port} (Linux)")
        return success

    def cleanup_all_rules(self) -> int:
        """
        Remove ALL Sentinel iptables rules.
        """
        if not self.is_compatible():
            return 0

        removed = 0
        try:
            # List all rules with line numbers
            cmd = ["sudo", "iptables", "-L", "INPUT", "-n", "--line-numbers"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise CleanupError("Failed to list iptables rules")

            # Parse from bottom to top to avoid line number shifting
            lines = result.stdout.strip().split('\n')
            to_delete = []
            for line in lines:
                if "Sentinel_Block_" in line:
                    parts = line.split()
                    if len(parts) > 0 and parts[0].isdigit():
                        to_delete.append(int(parts[0]))
            
            to_delete.sort(reverse=True)
            
            for line_num in to_delete:
                del_cmd = ["sudo", "iptables", "-D", "INPUT", str(line_num)]
                del_res = subprocess.run(del_cmd, capture_output=True, text=True, timeout=10)
                if del_res.returncode == 0:
                    removed += 1
                else:
                    logger.warning(f"Failed to delete rule at line {line_num}: {del_res.stderr}")

            logger.info(f"Cleanup complete: removed {removed} Sentinel iptables rules")

        except Exception as e:
            logger.error(f"iptables cleanup error: {e}")
            raise CleanupError(f"Failed to clean up iptables rules: {e}")

        return removed
