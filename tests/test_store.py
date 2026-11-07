import sqlite3

from mouse_gestures.events import MouseEvent
from mouse_gestures.store import EventStore


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
