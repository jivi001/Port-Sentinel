"""
Application Event Bus — Publish/Subscribe event dispatcher.

Provides loosely-coupled communication between application components.
Domain events are published by command handlers and consumed by
event handlers without direct coupling.

Thread-safe for use with the async dispatcher loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Type

from backend.domain.events.events import DomainEvent
from backend.domain.interfaces.services import IEventBus

logger = logging.getLogger("vigilant.events.bus")


class EventBus(IEventBus):
    """
    In-process event bus with synchronous and async handler support.

    Handlers are invoked in registration order. Exceptions in one
    handler do not prevent other handlers from executing.
    """

    def __init__(self) -> None:
        self._handlers: Dict[Type, List[Callable]] = defaultdict(list)
        self._async_handlers: Dict[Type, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def publish(self, event: Any) -> None:
        """Publish a domain event to all synchronous subscribers."""
        event_type = type(event)
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Event handler %s failed for %s",
                    handler.__name__,
                    event_type.__name__,
                )

    async def publish_async(self, event: Any) -> None:
        """Publish a domain event to all async subscribers."""
        event_type = type(event)
        with self._lock:
            handlers = list(self._async_handlers.get(event_type, []))
            sync_handlers = list(self._handlers.get(event_type, []))

        # Run sync handlers first
        for handler in sync_handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Sync handler %s failed for %s",
                    handler.__name__,
                    event_type.__name__,
                )

        # Then async handlers
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "Async handler %s failed for %s",
                    handler.__name__,
                    event_type.__name__,
                )

    def subscribe(
        self, event_type: type, handler: Callable[[Any], None]
    ) -> None:
        """Subscribe a synchronous handler to an event type."""
        with self._lock:
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)

    def subscribe_async(
        self, event_type: type, handler: Callable
    ) -> None:
        """Subscribe an async handler to an event type."""
        with self._lock:
            if handler not in self._async_handlers[event_type]:
                self._async_handlers[event_type].append(handler)

    def unsubscribe(
        self, event_type: type, handler: Callable[[Any], None]
    ) -> None:
        """Remove a handler subscription."""
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)
            async_handlers = self._async_handlers.get(event_type, [])
            if handler in async_handlers:
                async_handlers.remove(handler)

    def clear(self) -> None:
        """Remove all handler subscriptions."""
        with self._lock:
            self._handlers.clear()
            self._async_handlers.clear()

    @property
    def handler_count(self) -> int:
        """Total number of registered handlers."""
        with self._lock:
            sync = sum(len(h) for h in self._handlers.values())
            async_ = sum(len(h) for h in self._async_handlers.values())
            return sync + async_
