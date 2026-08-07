"""
Plugin Architecture — Base class for monitor plugins.

All future monitors (DNS, USB, Kernel, etc.) should extend
BaseMonitorPlugin and be placed in the plugins/ directory
for auto-discovery by the PluginRegistry.
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("vigilant.plugins")


class BaseMonitorPlugin(abc.ABC):
    """
    Abstract base class for all monitor plugins.

    Lifecycle:
        1. __init__ — Plugin constructed (no side effects)
        2. start() — Plugin begins monitoring
        3. get_data() — Called periodically to collect data
        4. stop() — Plugin stops and releases resources

    Subclasses must implement all abstract methods.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""
        ...

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Brief description of what this plugin monitors."""
        ...

    @property
    def version(self) -> str:
        """Plugin version string."""
        return "1.0.0"

    @property
    def enabled(self) -> bool:
        """Whether this plugin is currently enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def __init__(self) -> None:
        self._enabled = True
        self._started = False

    @abc.abstractmethod
    def start(self) -> None:
        """Start monitoring. Called once during application startup."""
        ...

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop monitoring and release resources. Called during shutdown."""
        ...

    @abc.abstractmethod
    def get_data(self) -> Dict[str, Any]:
        """Collect current monitoring data."""
        ...

    def health_check(self) -> bool:
        """Return True if the plugin is functioning correctly."""
        return self._started
