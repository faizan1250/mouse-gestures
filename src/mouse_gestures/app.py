from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from pathlib import Path

from .detector import ShakeDetector
from .events import MouseEvent
from .listener import MouseListener
from .ring import EventRing
from .store import EventStore

ShakeCallback = Callable[[list[MouseEvent]], None]

DRAIN_TIMEOUT_S = 0.05


class App:
    """Consumer loop: owns ring + detector + store. Only thread that touches them."""

    def __init__(
        self,
        db_path: str | Path = "mouse_events.db",
        on_shake: ShakeCallback | None = None,
    ) -> None:
        self.inbox: queue.Queue[MouseEvent] = queue.Queue()
        self.ring = EventRing()
        self.detector = ShakeDetector()
        self.store = EventStore(db_path)
        self.on_shake = on_shake
        self.listener = MouseListener(self.inbox)
        self._stop = threading.Event()

    def drain_once(self) -> int:
        """Drain inbox, persist + detect. Returns events processed. Fires on_shake only on positive detection; None means no callback."""
        batch: list[MouseEvent] = []
        try:
            batch.append(self.inbox.get(timeout=DRAIN_TIMEOUT_S))
        except queue.Empty:
            return 0
        while True:
            try:
                batch.append(self.inbox.get_nowait())
            except queue.Empty:
                break
        for event in batch:
            self.ring.append(event)
            self.store.append(event)
        self.store.flush()
        snapshot = self.ring.snapshot()
        if self.detector.check(snapshot) and self.on_shake is not None:
            self.on_shake(snapshot)
        for _ in batch:
            self.inbox.task_done()
        return len(batch)

    def run(self) -> None:
        self.listener.start()
        try:
            while not self._stop.is_set():
                self.drain_once()
        finally:
            self.listener.stop()
            self.store.flush()

    def stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        self.store.close()


def main() -> None:
    app = App(on_shake=lambda events: print(f"shake detected ({len(events)} in ring)"))
    try:
        app.run()
    except KeyboardInterrupt:
        app.stop()
    finally:
        app.close()


if __name__ == "__main__":
    main()
