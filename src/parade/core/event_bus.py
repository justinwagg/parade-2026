import asyncio
import logging
from collections import defaultdict
from typing import Callable, Awaitable
from .events import Event

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[..., Awaitable]) -> None:
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        try:
            self._handlers[event_type].remove(handler)
        except ValueError:
            pass

    async def publish(self, event: Event) -> None:
        handlers = list(self._handlers.get(event.event_type, []))
        if handlers:
            results = await asyncio.gather(
                *(h(event) for h in handlers),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    logger.error(
                        "Event handler error for %s: %s", event.event_type, r
                    )

    def publish_from_thread(self, event: Event) -> None:
        """Thread-safe: schedule publish on the running event loop."""
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self.publish(event))
        )
