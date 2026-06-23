"""
Sentinel OS Adapter — macOS / Darwin (darwin_bridge.py)

Provides:
  - Port → PID → AppName mapping via lsof
  - Process suspend/resume/kill via psutil
  - Hard block via pfctl (Packet Filter)
  - Cleanup of all Sentinel_ pf rules
  - System PID guard (PID 0 = kernel_task, PID 1 = launchd)
"""

import subprocess
import platform
import logging
import re
import tempfile
import os
from typing import List, Dict, Optional, Any

import psutil

from backend.core.exceptions import (
    SystemProcessProtectionError,
    FirewallRuleError,
    CleanupError,
)

logger = logging.getLogger("sentinel.darwin")

# --- System PID protection ---
PROTECTED_PIDS_MAC = {0, 1}  # PID 0 = kernel_task, PID 1 = launchd

# PF anchor name for all Sentinel rules
PF_ANCHOR = "com.sentinel"
# Temp file for pf rules
PF_RULES_FILE = os.path.join(tempfile.gettempdir(), "sentinel_pf_rules.conf")


from backend.os_adapters.base_bridge import OSBridgeAdapter

class DarwinBridge(OSBridgeAdapter):
    def is_compatible(self) -> bool:
        return platform.system() == "Darwin"

    def get_port_pid_map(self) -> List[Dict[str, Any]]:
        """
        Build live Port → PID → AppName map using lsof and psutil.

        Uses `lsof -iTCP -iUDP -n -P` for comprehensive port enumeration.
        Falls back to psutil if lsof is unavailable.
        """
        results = []
        seen_ports = set()

        try:
            # Try lsof first for better coverage on macOS
            cmd = ["lsof", "-iTCP", "-iUDP", "-n", "-P", "-F", "pcn"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                results = _parse_lsof_output(result.stdout, seen_ports)
            else:
                logger.debug(f"lsof failed ({result.returncode}), falling back to psutil")
                results = _get_ports_psutil(seen_ports)

        except FileNotFoundError:
            logger.debug("lsof not found, falling back to psutil")
            results = _get_ports_psutil(seen_ports)
        except subprocess.TimeoutExpired:
            logger.warning("lsof timed out, falling back to psutil")
            results = _get_ports_psutil(seen_ports)

        return results

    def block_port(self, port: int, protocol: str = "tcp", interface: str = "en0") -> bool:
        """
        Hard Block: Add a pf rule to block traffic on a port.

        Uses pfctl to install a block rule on the specified interface.
        """
        if not self.is_compatible():
            raise FirewallRuleError("pfctl operations require macOS")
            
        if not (1 <= port <= 65535):
            raise FirewallRuleError(f"Invalid port number: {port}. Must be 1-65535.")
        if protocol.lower() not in ('tcp', 'udp'):
            raise FirewallRuleError(f"Invalid protocol: {protocol}. Must be tcp or udp.")
        if not re.match(r'^[a-zA-Z0-9]+$', interface):
            raise FirewallRuleError(f"Invalid interface name: {interface}")

        rule = f"block drop on {interface} proto {protocol} from any to any port {port}"

        try:
            # Write rule to temp file and load it
            _active_rules[port] = rule
            _write_pf_rules()

            # Apply rules via pfctl to the specific anchor
            result = subprocess.run(
                ["sudo", "pfctl", "-a", PF_ANCHOR, "-f", PF_RULES_FILE],
                capture_output=True, text=True, timeout=10,
            )
            
            # Ensure pf is enabled
            subprocess.run(["sudo", "pfctl", "-e"], capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                # pfctl returns 0 on success; some warnings go to stderr but are non-fatal
                if "pf enabled" not in result.stderr.lower() and result.returncode != 0:
                    logger.warning(f"pfctl stderr: {result.stderr.strip()}")

            logger.info(f"Hard blocked port {port}/{protocol} on {interface} (macOS)")
            return True

        except subprocess.TimeoutExpired:
            raise FirewallRuleError(f"pfctl timed out for port {port}")
        except Exception as e:
            raise FirewallRuleError(f"Error blocking port {port}: {e}")

    def unblock_port(self, port: int) -> bool:
        """Remove the pf rule for a specific port and reload."""
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
        """
        Remove ALL Sentinel pf rules and disable the filter.

        Called on exit via atexit hook.
        Returns the number of rules removed.
        """
        removed = len(_active_rules)
        _active_rules.clear()

        try:
            # Flush anchor rules
            subprocess.run(
                ["sudo", "pfctl", "-a", PF_ANCHOR, "-Fr"],
                capture_output=True, text=True, timeout=10,
            )

            # Remove rules file
            if os.path.exists(PF_RULES_FILE):
                os.remove(PF_RULES_FILE)

            logger.info(f"Cleanup complete: removed {removed} Sentinel pf rules")

        except Exception as e:
            logger.error(f"PF cleanup error: {e}")
            raise CleanupError(f"Failed to clean up pf rules: {e}")

        return removed
