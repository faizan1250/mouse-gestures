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


def circle_events(n=48, cx=500, cy=400, r=120, step_ms=16, start_ms=2_000_000):
    import math

    return [
        MouseEvent(
            ts_ms=start_ms + i * step_ms,
            x=int(cx + r * math.cos(2.0 * math.pi * i / n)),
            y=int(cy + r * math.sin(2.0 * math.pi * i / n)),
        )
        for i in range(n + 1)
    ]


def triangle_events(n_edge=16, step_ms=16, start_ms=2_000_000):
    corners = [(400, 520), (640, 520), (520, 300), (400, 520)]
    events = []
    ts = start_ms
    for a, b in zip(corners, corners[1:]):
        for i in range(n_edge):
            t = i / n_edge
            events.append(
                MouseEvent(
                    ts_ms=ts,
                    x=int(a[0] + t * (b[0] - a[0])),
                    y=int(a[1] + t * (b[1] - a[1])),
                )
            )
            ts += step_ms
    events.append(MouseEvent(ts_ms=ts, x=corners[-1][0], y=corners[-1][1]))
    return events


def delete_events(n_leg=12, step_ms=16, start_ms=2_000_000):
    corners = [(420, 320), (620, 320), (420, 400), (620, 400), (420, 480), (620, 480)]
    events = []
    ts = start_ms
    for a, b in zip(corners, corners[1:]):
        for i in range(n_leg):
            t = i / n_leg
            events.append(
                MouseEvent(
                    ts_ms=ts,
                    x=int(a[0] + t * (b[0] - a[0])),
                    y=int(a[1] + t * (b[1] - a[1])),
                )
            )
            ts += step_ms
    events.append(MouseEvent(ts_ms=ts, x=corners[-1][0], y=corners[-1][1]))
    return events
