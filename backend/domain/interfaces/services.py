"""
Domain Interfaces — Service abstract base classes.

Defines contracts for infrastructure services that the domain and
application layers can depend upon without coupling to implementations.
"""

from __future__ import annotations

import abc
from typing import Any, Callable, Dict, List, Optional


class INetworkCapture(abc.ABC):
    """Interface for the packet capture subsystem."""

    @abc.abstractmethod
    def start(self) -> None:
        """Start the network capture process."""
        ...

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop the network capture process."""
        ...

    @abc.abstractmethod
    def is_alive(self) -> bool:
        """Return True if the capture process is running."""
        ...


class IFirewallAdapter(abc.ABC):
    """Interface for OS-level firewall operations."""

    @abc.abstractmethod
    def is_compatible(self) -> bool: ...

    @abc.abstractmethod
    def is_elevated(self) -> bool: ...

    @abc.abstractmethod
    def block_port(self, port: int, protocol: str = "tcp") -> bool: ...

    @abc.abstractmethod
    def unblock_port(self, port: int) -> bool: ...

    @abc.abstractmethod
    def cleanup_all_rules(self) -> int: ...

    @abc.abstractmethod
    def get_port_pid_map(self) -> List[Dict[str, Any]]: ...

    @abc.abstractmethod
    def get_process_info(self, pid: int) -> Dict[str, Any]: ...


class IThreatIntelProvider(abc.ABC):
    """Interface for threat intelligence lookups."""

    @abc.abstractmethod
    def get_ip_metadata(self, ip: str) -> dict: ...

    @abc.abstractmethod
    def get_risk_score(self, ip: str) -> int: ...

    @abc.abstractmethod
    def is_malicious(self, ip: str) -> bool: ...


class IEventBus(abc.ABC):
    """Interface for the application event bus (publish/subscribe)."""

    @abc.abstractmethod
    def publish(self, event: Any) -> None:
        """Publish a domain event to all subscribed handlers."""
        ...

    @abc.abstractmethod
    def subscribe(
        self, event_type: type, handler: Callable[[Any], None]
    ) -> None:
        """Subscribe a handler to a specific event type."""
        ...

    @abc.abstractmethod
    def unsubscribe(
        self, event_type: type, handler: Callable[[Any], None]
    ) -> None:
        """Remove a handler subscription."""
        ...
