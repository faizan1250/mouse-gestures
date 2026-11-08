from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from pathlib import Path

from .detector import ShakeDetector
from .events import MouseEvent
from .listener import MouseListener
from .ring import EventRing
from .shapes import ShapeRecognizer, ShapeSegmenter
from .store import RETENTION_MS, EventStore

ShakeCallback = Callable[[list[MouseEvent]], None]
ShapeCallback = Callable[[str, float, list[MouseEvent]], None]

DRAIN_TIMEOUT_S = 0.05


class App:
    """Consumer loop: owns ring + detector + store. Only thread that touches them."""

    def __init__(
        self,
        db_path: str | Path = "mouse_events.db",
        on_shake: ShakeCallback | None = None,
        on_shape: ShapeCallback | None = None,
    ) -> None:
        self.inbox: queue.Queue[MouseEvent] = queue.Queue()
        self.ring = EventRing()
        self.detector = ShakeDetector()
        self.store = EventStore(db_path)
        self.on_shake = on_shake
        self.on_shape = on_shape
        self.recognizer = ShapeRecognizer()
        self.segmenter = ShapeSegmenter()
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
        # Retention relative to newest ingested event; no wall-clock, no extra thread.
        self.store.prune_older_than(batch[-1].ts_ms - RETENTION_MS)
        snapshot = self.ring.snapshot()
        if self.detector.check(snapshot) and self.on_shake is not None:
            self.on_shake(snapshot)
        for segment in self.segmenter.feed(batch):
            name, score = self.recognizer.recognize_events(segment)
            if name is not None and self.on_shape is not None:
                self.on_shape(name, score, segment)
        for _ in batch:
            self.inbox.task_done()
        return len(batch)

    def flush_shapes(self) -> None:
        """Recognize the trailing idle segment, if long enough. Fires on_shape on match."""
        segment = self.segmenter.flush()
        if not segment:
            return
        name, score = self.recognizer.recognize_events(segment)
        if name is not None and self.on_shape is not None:
            self.on_shape(name, score, segment)

    def run(self) -> None:
        self.listener.start()
        try:
            while not self._stop.is_set():
                self.drain_once()
        finally:
            self.listener.stop()
            # Teardown has no later idle gap; flush trailing segment. Mid-run trailing fires on next idle gap (800ms pump deferred).
            self.flush_shapes()
            self.store.flush()

    def stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        self.store.close()


def main() -> None:
    app = App(
        on_shake=lambda events: print(f"shake detected ({len(events)} in ring)"),
        on_shape=lambda name, score, events: print(f"shape: {name} ({score:.2f}, {len(events)} pts)"),
    )
    try:
        app.run()
    except KeyboardInterrupt:
        app.stop()
    finally:
        app.close()


if __name__ == "__main__":
    main()
