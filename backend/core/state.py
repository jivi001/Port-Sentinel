"""
Vigilant Core State — Global singleton accessors for shared runtime state.

Provides thread-safe access to:
  - Database instance
  - Traffic accumulator
  - Policy engine
  - OS bridge adapter
  - Sniffer process

These are initialized in main.py lifespan and accessed by route modules
via the getter functions below, avoiding circular imports.
"""

from typing import Optional, Any

# --- Singleton references (set during startup lifespan) ---
_db: Any = None
_traffic_accumulator: Any = None
_policy_engine: Any = None
_os_bridge: Any = None
_sniffer_process: Any = None


def init_state(
    db,
    traffic_accumulator,
    policy_engine,
    os_bridge,
    sniffer_process=None,
) -> None:
    """Initialize global state references during application startup."""
    global _db, _traffic_accumulator, _policy_engine, _os_bridge, _sniffer_process
    _db = db
    _traffic_accumulator = traffic_accumulator
    _policy_engine = policy_engine
    _os_bridge = os_bridge
    _sniffer_process = sniffer_process


def set_sniffer_process(proc) -> None:
    """Update the sniffer process reference (may start after init)."""
    global _sniffer_process
    _sniffer_process = proc


def get_traffic_accumulator():
    """Return the shared TrafficAccumulator instance."""
    return _traffic_accumulator


def get_policy_engine():
    """Return the PolicyEngine instance."""
    return _policy_engine


def get_os_bridge():
    """Return the OS bridge adapter (or None if unsupported platform)."""
    return _os_bridge


def get_sniffer_process():
    """Return the sniffer process (or None if not started)."""
    return _sniffer_process
