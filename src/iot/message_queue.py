"""Fila limitada de mensagens MQTT (proteção contra flood)."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Deque

logger = logging.getLogger(__name__)

MessageItem = tuple[str, bytes]


@dataclass
class BoundedMessageQueue:
    """Descarta novos itens quando ``max_size`` é atingido (com log estruturado)."""

    max_size: int = 100
    _items: Deque[MessageItem] = field(default_factory=deque, repr=False)

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return True

    def offer(self, topic: str, payload: bytes) -> bool:
        if len(self._items) >= self.max_size:
            logger.warning(
                "iot_queue_drop",
                extra={
                    "topic": topic,
                    "queue_size": len(self._items),
                    "max_queue_size": self.max_size,
                },
            )
            return False
        self._items.append((topic, payload))
        return True

    def pop(self) -> MessageItem | None:
        if not self._items:
            return None
        return self._items.popleft()