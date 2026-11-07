from mouse_gestures.app import App
from mouse_gestures.events import MouseEvent


def shake_events(n_swings=8, x0=100, swing=120, step_ms=40, start_ms=1_000_000, y=400):
    events = []
    x = x0
    direction = 1
    for i in range(n_swings * 2 + 1):
        events.append(MouseEvent(ts_ms=start_ms + i * step_ms, x=x, y=y))
        x += direction * swing
        direction *= -1
    return events


def drift_events(n=20, start_ms=1_000_000):
    return [MouseEvent(ts_ms=start_ms + i * 40, x=100 + i * 2, y=400) for i in range(n)]


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
