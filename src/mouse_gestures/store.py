from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path

from .events import MouseEvent

SCHEMA = """
CREATE TABLE IF NOT EXISTS mouse_events (
  ts_ms INTEGER NOT NULL,
  x INTEGER NOT NULL,
  y INTEGER NOT NULL,
  buttons TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mouse_events_ts ON mouse_events (ts_ms);
"""

BATCH_SIZE = 100

# TODO(slice2): auto-prune rows older than 7 days (default retention).


class EventStore:
    """SQLite WAL logger. One connection, used only on the consumer thread."""

    def __init__(self, path: str | Path, batch_size: int = BATCH_SIZE) -> None:
        self.path = Path(path)
        self.batch_size = batch_size
        self._conn = sqlite3.connect(str(self.path), check_same_thread=True)
        try:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.executescript(SCHEMA)
            self._conn.commit()
        except Exception:
            self._conn.close()
            raise
        self._restrict_permissions()
        self._pending = 0
        self._closed = False

    def _restrict_permissions(self) -> None:
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    @property
    def journal_mode(self) -> str:
        return self._conn.execute("PRAGMA journal_mode;").fetchone()[0]

    def append(self, event: MouseEvent) -> None:
        self._conn.execute(
            "INSERT INTO mouse_events (ts_ms, x, y, buttons) VALUES (?, ?, ?, ?)",
            (event.ts_ms, event.x, event.y, event.buttons),
        )
        self._pending += 1
        if self._pending >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        self._conn.commit()
        self._pending = 0

    def count(self) -> int:
        self.flush()
        return self._conn.execute("SELECT COUNT(*) FROM mouse_events").fetchone()[0]

    def fetch_since(self, since_ms: int) -> list[tuple[int, int, int, str]]:
        self.flush()
        return self._conn.execute(
            "SELECT ts_ms, x, y, buttons FROM mouse_events WHERE ts_ms >= ? ORDER BY ts_ms",
            (since_ms,),
        ).fetchall()

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._conn.commit()
        finally:
            self._conn.close()
            self._pending = 0
            self._closed = True
