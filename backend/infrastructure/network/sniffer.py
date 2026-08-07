"""
Infrastructure Network — Packet sniffer process.
Re-exports the core sniffer to maintain compatibility while
moving it to the infrastructure layer.
"""

from backend.core.sniffer import SnifferProcess

__all__ = ["SnifferProcess"]
