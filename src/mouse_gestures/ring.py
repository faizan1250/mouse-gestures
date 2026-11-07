from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence

from .events import MouseEvent

RING_MAXLEN = 512


class EventRing:
    """Consumer-thread-owned ring buffer. Never touched by the listener thread."""

    def __init__(self, maxlen: int = RING_MAXLEN) -> None:
        self._buf: deque[MouseEvent] = deque(maxlen=maxlen)

    def append(self, event: MouseEvent) -> None:
        self._buf.append(event)

    def extend(self, events: Iterable[MouseEvent]) -> None:
        self._buf.extend(events)

    def snapshot(self) -> list[MouseEvent]:
        return list(self._buf)

    def __len__(self) -> int:
        return len(self._buf)

    def window(self, since_ms: int) -> list[MouseEvent]:
        return [e for e in self._buf if e.ts_ms >= since_ms]
