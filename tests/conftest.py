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
