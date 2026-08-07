"""
Plugin Registry — Auto-discovery and lifecycle management.

Discovers, loads, and manages monitor plugins. Plugins can be
registered manually or auto-discovered from the plugins/ directory.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Type

from backend.plugins.base import BaseMonitorPlugin

logger = logging.getLogger("vigilant.plugins.registry")


class PluginRegistry:
    """
    Manages plugin lifecycle: discovery → registration → start → stop.

    Usage:
        registry = PluginRegistry()
        registry.discover()
        registry.start_all()
        # ... application runs ...
        registry.stop_all()
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, BaseMonitorPlugin] = {}

    def register(self, plugin: BaseMonitorPlugin) -> None:
        """Register a plugin instance."""
        name = plugin.name
        if name in self._plugins:
            logger.warning("Plugin '%s' already registered, skipping", name)
            return
        self._plugins[name] = plugin
        logger.info("Plugin registered: %s v%s", name, plugin.version)

    def discover(self, package_path: Optional[str] = None) -> int:
        """
        Auto-discover plugins in the plugins/ directory.

        Scans for Python modules containing classes that extend
        BaseMonitorPlugin.

        Returns number of plugins discovered.
        """
        if package_path is None:
            package_path = str(Path(__file__).parent)

        count = 0
        for importer, module_name, is_pkg in pkgutil.iter_modules([package_path]):
            if module_name.startswith("_") or module_name in ("base", "registry"):
                continue
            try:
                module = importlib.import_module(f"backend.plugins.{module_name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseMonitorPlugin)
                        and attr is not BaseMonitorPlugin
                    ):
                        instance = attr()
                        self.register(instance)
                        count += 1
            except Exception:
                logger.exception("Failed to load plugin module: %s", module_name)
        return count

    def start_all(self) -> None:
        """Start all enabled plugins."""
        for name, plugin in self._plugins.items():
            if plugin.enabled:
                try:
                    plugin.start()
                    plugin._started = True
                    logger.info("Plugin started: %s", name)
                except Exception:
                    logger.exception("Failed to start plugin: %s", name)

    def stop_all(self) -> None:
        """Stop all running plugins."""
        for name, plugin in self._plugins.items():
            if plugin._started:
                try:
                    plugin.stop()
                    plugin._started = False
                    logger.info("Plugin stopped: %s", name)
                except Exception:
                    logger.exception("Failed to stop plugin: %s", name)

    def get_plugin(self, name: str) -> Optional[BaseMonitorPlugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> List[dict]:
        """Get status of all registered plugins."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "version": p.version,
                "enabled": p.enabled,
                "running": p._started,
                "healthy": p.health_check(),
            }
            for p in self._plugins.values()
        ]

    @property
    def count(self) -> int:
        return len(self._plugins)
