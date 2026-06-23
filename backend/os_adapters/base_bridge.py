"""
Vigilant OS Adapter — Abstract Base Class.

Defines the unified interface for all platform-specific bridges
(Windows, Linux, macOS). Each bridge must implement:
  - Network port/PID discovery
  - Process information retrieval (detection only — no termination)
  - Firewall rule management
  - Privilege detection
"""

import abc
from typing import List, Dict, Any


class OSBridgeAdapter(abc.ABC):
    """
    Abstract Base Class for OS-specific adapters.

    All platform bridges (win32, linux, darwin) must implement
    this interface to ensure cross-platform compatibility.
    """

    @abc.abstractmethod
    def is_compatible(self) -> bool:
        """Check if this adapter is compatible with the current OS."""
        pass

    @abc.abstractmethod
    def is_elevated(self) -> bool:
        """Check if the process has elevated privileges (admin/root)."""
        pass

    @abc.abstractmethod
    def get_port_pid_map(self) -> List[Dict[str, Any]]:
        """
        Build a live Port → PID → AppName map.

        Returns:
            List of dicts: {"port", "pid", "app_name", "protocol", "status"}
        """
        pass

    @abc.abstractmethod
    def get_process_info(self, pid: int) -> Dict[str, Any]:
        """
        Get information about a process (detection only — no termination).

        Args:
            pid: Process ID to inspect.

        Returns:
            Dict with: {"pid", "name", "status", "cpu_percent",
                         "memory_mb", "create_time", "connections"}
        """
        pass

    @abc.abstractmethod
    def block_port(self, port: int, protocol: str = "tcp") -> bool:
        """
        Add a firewall rule to hard block traffic on a specific port.

        Args:
            port: Port number to block (1-65535).
            protocol: Protocol (tcp/udp).

        Returns:
            True if the rule was created successfully.

        Raises:
            FirewallRuleError: If the operation fails.
        """
        pass

    @abc.abstractmethod
    def unblock_port(self, port: int) -> bool:
        """
        Remove the firewall rule for a specific port.

        Args:
            port: Port number to unblock.

        Returns:
            True if the rule was removed.
        """
        pass

    @abc.abstractmethod
    def cleanup_all_rules(self) -> int:
        """
        Remove ALL Vigilant-created firewall rules.

        Called on graceful shutdown to ensure no ports remain blocked.

        Returns:
            Number of rules removed.
        """
        pass
