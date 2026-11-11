from collections.abc import Callable

from .models import YBYEvent


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[YBYEvent], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[YBYEvent], None]) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: YBYEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
