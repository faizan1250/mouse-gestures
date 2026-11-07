from conftest import drift_events, shake_events
from mouse_gestures.app import App


def test_drain_persists_and_fires_on_shake(tmp_path):
    fired: list = []
    app = App(db_path=tmp_path / "events.db", on_shake=fired.append)
    try:
        events = shake_events()
        for event in events:
            app.inbox.put(event)
        assert app.drain_once() == len(events)
        assert app.store.count() == len(events)
        assert len(fired) == 1
    finally:
        app.close()


def test_drain_persists_without_fire_on_drift(tmp_path):
    fired: list = []
    app = App(db_path=tmp_path / "events.db", on_shake=fired.append)
    try:
        events = drift_events()
        for event in events:
            app.inbox.put(event)
        assert app.drain_once() == len(events)
        assert app.store.count() == len(events)
        assert fired == []
    finally:
        app.close()


def test_drain_empty_returns_zero(tmp_path):
    fired: list = []
    app = App(db_path=tmp_path / "events.db", on_shake=fired.append)
    try:
        assert app.drain_once() == 0
        assert app.store.count() == 0
        assert fired == []
    finally:
        app.close()


def test_ring_window_filters_by_timestamp(tmp_path):
    app = App(db_path=tmp_path / "events.db", on_shake=None)
    try:
        events = shake_events()
        for event in events:
            app.inbox.put(event)
        app.drain_once()
        cutoff = events[len(events) // 2].ts_ms
        windowed = app.ring.window(cutoff)
        assert 0 < len(windowed) < len(events)
        assert all(e.ts_ms >= cutoff for e in windowed)
    finally:
        app.close()
