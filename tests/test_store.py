import sqlite3

from mouse_gestures.events import MouseEvent, now_ms
from mouse_gestures.store import RETENTION_MS, EventStore


def test_journal_mode_is_wal(tmp_path):
    store = EventStore(tmp_path / "events.db")
    try:
        assert store.journal_mode.lower() == "wal"
    finally:
        store.close()


def test_batch_insert_and_index(tmp_path):
    db = tmp_path / "events.db"
    store = EventStore(db, batch_size=10)
    try:
        for i in range(25):
            store.append(MouseEvent(ts_ms=1_000_000 + i, x=i, y=i, buttons="none"))
        assert store.count() == 25
        assert len(store.fetch_since(1_000_010)) == 15
        idx = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_mouse_events_ts'"
        ).fetchone()
        assert idx is not None
    finally:
        store.close()


def test_buttons_roundtrip_and_param_query(tmp_path):
    store = EventStore(tmp_path / "events.db")
    try:
        store.append(MouseEvent(ts_ms=1, x=10, y=20, buttons="left|right"))
        rows = store.fetch_since(0)
        assert rows[0][3] == "left|right"
    finally:
        store.close()


def test_close_idempotent(tmp_path):
    store = EventStore(tmp_path / "events.db")
    store.close()
    store.close()


def test_prune_removes_only_rows_older_than_cutoff(tmp_path):
    store = EventStore(tmp_path / "events.db")
    try:
        now = now_ms()
        store.append(MouseEvent(ts_ms=now - RETENTION_MS - 60_000, x=1, y=1))
        store.append(MouseEvent(ts_ms=now - RETENTION_MS, x=2, y=2))
        store.append(MouseEvent(ts_ms=now, x=3, y=3))
        assert store.prune_older_than(now - RETENTION_MS) == 1
        assert store.count() == 2
    finally:
        store.close()
