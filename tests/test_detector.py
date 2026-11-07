from mouse_gestures.detector import COOLDOWN_MS, ShakeDetector
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


def test_fires_on_shake():
    assert ShakeDetector().check(shake_events())


def test_no_fire_on_slow_drift():
    assert not ShakeDetector().check(drift_events())


def test_no_fire_on_straight_fast_line():
    events = [MouseEvent(ts_ms=1_000_000 + i * 20, x=100 + i * 30, y=400) for i in range(20)]
    assert not ShakeDetector().check(events)


def test_no_fire_below_crossing_threshold():
    assert not ShakeDetector().check(shake_events(n_swings=2))


def test_cooldown_suppresses_repeat():
    detector = ShakeDetector()
    events = shake_events()
    assert detector.check(events)
    later = [MouseEvent(ts_ms=e.ts_ms + COOLDOWN_MS // 3, x=e.x, y=e.y) for e in events]
    assert not detector.check(events + later)


def test_cooldown_allows_refire_after_expiry():
    detector = ShakeDetector()
    events = shake_events()
    assert detector.check(events)
    later = [MouseEvent(ts_ms=e.ts_ms + COOLDOWN_MS + 2000, x=e.x, y=e.y) for e in events]
    assert detector.check(events + later)
