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
from typing import List, Dict, Optional

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


def is_darwin() -> bool:
    """Check if running on macOS."""
    return platform.system() == "Darwin"


def _check_system_pid(pid: int, operation: str) -> None:
    """Raise SystemProcessProtectionError for protected PIDs."""
    if pid in PROTECTED_PIDS_MAC:
        raise SystemProcessProtectionError(pid, operation)


# --- Port → PID → AppName Mapping ---

def get_port_pid_map() -> List[Dict[str, any]]:
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


def _parse_lsof_output(output: str, seen_ports: set) -> List[Dict]:
    """Parse lsof -F output format."""
    results = []
    current_pid = 0
    current_name = "Unknown"

    for line in output.strip().split('\n'):
        if not line:
            continue
        marker = line[0]
        value = line[1:]

        if marker == 'p':
            current_pid = int(value)
        elif marker == 'c':
            current_name = value
        elif marker == 'n':
            # Parse network name: e.g., "*:8080" or "127.0.0.1:3000"
            match = re.search(r':(\d+)$', value)
            if match:
                port = int(match.group(1))
                if port not in seen_ports:
                    seen_ports.add(port)
                    results.append({
                        "port": port,
                        "pid": current_pid,
                        "app_name": current_name,
                        "protocol": "TCP",  # lsof -iTCP covers TCP
                        "status": "LISTEN",
                    })

    return results


def _get_ports_psutil(seen_ports: set) -> List[Dict]:
    """Fallback: get port map via psutil."""
    results = []
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


def _resolve_pid_name(pid: int) -> str:
    """Resolve PID to application name."""
    if pid in PROTECTED_PIDS_MAC:
        return "System"
    try:
        proc = psutil.Process(pid)
        return proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "Unknown"


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


# --- Firewall — Hard Block (pfctl) ---

# Track active Sentinel rules for cleanup
_active_rules: Dict[int, str] = {}  # port -> rule string


def block_port(port: int, protocol: str = "tcp", interface: str = "en0") -> bool:
    """
    Hard Block: Add a pf rule to block traffic on a port.

    Uses pfctl to install a block rule on the specified interface.
    """
    if not is_darwin():
        raise FirewallRuleError("pfctl operations require macOS")

    rule = f"block drop on {interface} proto {protocol} from any to any port {port}"

    try:
        # Write rule to temp file and load it
        _active_rules[port] = rule
        _write_pf_rules()

        # Apply rules via pfctl
        result = subprocess.run(
            ["sudo", "pfctl", "-ef", PF_RULES_FILE],
            capture_output=True, text=True, timeout=10,
        )

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


def unblock_port(port: int) -> bool:
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


def _write_pf_rules() -> None:
    """Write all active Sentinel rules to the PF rules file."""
    with open(PF_RULES_FILE, 'w') as f:
        f.write(f"# Sentinel PF Rules (auto-generated)\n")
        for port, rule in sorted(_active_rules.items()):
            f.write(f"{rule}\n")


def _reload_pf() -> None:
    """Reload pf with current rules or disable if no rules."""
    try:
        if _active_rules:
            subprocess.run(
                ["sudo", "pfctl", "-ef", PF_RULES_FILE],
                capture_output=True, text=True, timeout=10,
            )
        else:
            # No rules: disable pf and clean up
            subprocess.run(
                ["sudo", "pfctl", "-d"],
                capture_output=True, text=True, timeout=10,
            )
            # Remove rules file
            if os.path.exists(PF_RULES_FILE):
                os.remove(PF_RULES_FILE)
    except Exception as e:
        logger.warning(f"PF reload error: {e}")


def cleanup_all_rules() -> int:
    """
    Remove ALL Sentinel pf rules and disable the filter.

    Called on exit via atexit hook.
    Returns the number of rules removed.
    """
    removed = len(_active_rules)
    _active_rules.clear()

    try:
        # Disable pf
        subprocess.run(
            ["sudo", "pfctl", "-d"],
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
