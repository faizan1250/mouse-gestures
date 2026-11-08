import math

import pytest
from conftest import circle_events, delete_events, drift_events, shake_events, triangle_events
from mouse_gestures.app import App
from mouse_gestures.shapes import (
    MIN_SHAPE_POINTS,
    SHAPE_IDLE_MS,
    SHAPE_SCORE_THRESHOLD,
    SHAPE_SQUARE_SIZE,
    RESAMPLE_N,
    TEMPLATES,
    ShapeRecognizer,
    ShapeSegmenter,
    distance_at_angle,
    distance_at_best_angle,
    normalize_points,
    path_distance,
    recognize_points,
    resample,
    rotate_points,
)


def test_resample_returns_n_even_points():
    pts = resample([(0.0, 0.0), (90.0, 0.0)])
    assert len(pts) == RESAMPLE_N
    assert pts[0] == pytest.approx((0.0, 0.0))
    assert pts[-1] == pytest.approx((90.0, 0.0))
    gaps = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    assert max(gaps) - min(gaps) < 1e-6


def test_resample_rejects_empty():
    with pytest.raises(ValueError):
        resample([])


def test_normalize_centers_and_scales():
    pts = normalize_points([(0.0, 100.0), (100.0, 100.0), (50.0, 0.0), (0.0, 100.0)])
    assert len(pts) == RESAMPLE_N
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    assert (cx, cy) == pytest.approx((0.0, 0.0))
    width = max(p[0] for p in pts) - min(p[0] for p in pts)
    height = max(p[1] for p in pts) - min(p[1] for p in pts)
    assert (width, height) == pytest.approx((SHAPE_SQUARE_SIZE, SHAPE_SQUARE_SIZE))


def test_best_angle_forgives_rotation():
    rotated = rotate_points(TEMPLATES["triangle"], math.radians(30.0))
    direct = distance_at_angle(rotated, TEMPLATES["triangle"], 0.0)
    best = distance_at_best_angle(rotated, TEMPLATES["triangle"])
    assert best < 1.0
    assert best < direct


def test_self_match_scores_near_one():
    for name, template in TEMPLATES.items():
        match, score = recognize_points(template)
        assert match == name
        assert score == pytest.approx(1.0, abs=0.05)


@pytest.mark.parametrize(
    ("gen", "name"),
    [(circle_events, "circle"), (triangle_events, "triangle"), (delete_events, "delete")],
)
def test_discriminates_generated_shapes(gen, name):
    events = gen()
    match, score = ShapeRecognizer().recognize_events(events)
    assert match == name
    assert score >= SHAPE_SCORE_THRESHOLD


def test_rejects_slow_drift():
    match, score = ShapeRecognizer().recognize_events(drift_events())
    assert match is None
    assert score < SHAPE_SCORE_THRESHOLD


def test_rejects_straight_fast_line():
    from mouse_gestures.events import MouseEvent

    line = [MouseEvent(ts_ms=1_000_000 + i * 20, x=100 + i * 30, y=400) for i in range(20)]
    match, score = ShapeRecognizer().recognize_events(line)
    assert match is None
    assert score < SHAPE_SCORE_THRESHOLD


def test_rejects_empty_input():
    assert ShapeRecognizer().recognize_events([]) == (None, 0.0)
    assert recognize_points([]) == (None, 0.0)


def test_path_distance_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        path_distance([(0.0, 0.0)], [(0.0, 0.0), (1.0, 1.0)])


def test_segments_split_on_idle_gap():
    first = circle_events(start_ms=1_000_000)
    second = triangle_events(start_ms=first[-1].ts_ms + SHAPE_IDLE_MS + 100)
    segmenter = ShapeSegmenter()
    completed = segmenter.feed(first + second)
    assert len(completed) == 1
    assert [e.ts_ms for e in completed[0]] == [e.ts_ms for e in first]
    assert [e.ts_ms for e in segmenter.pending] == [e.ts_ms for e in second]
    assert segmenter.flush() == second
    assert segmenter.pending == []


def test_segments_hold_trailing_until_gap_or_flush():
    events = circle_events(start_ms=1_000_000)
    segmenter = ShapeSegmenter()
    assert segmenter.feed(events) == []
    assert [e.ts_ms for e in segmenter.pending] == [e.ts_ms for e in events]
    assert segmenter.flush() == events


def test_segments_drop_short_fragments():
    from mouse_gestures.events import MouseEvent

    blip = [MouseEvent(ts_ms=1_000_000 + i * 16, x=500, y=400) for i in range(3)]
    assert len(blip) < MIN_SHAPE_POINTS
    rest = circle_events(start_ms=blip[-1].ts_ms + SHAPE_IDLE_MS + 100)
    segmenter = ShapeSegmenter()
    assert segmenter.feed(blip + rest) == []
    assert segmenter.flush() == rest


def test_empty_feed_and_flush_are_noops():
    segmenter = ShapeSegmenter()
    assert segmenter.feed([]) == []
    assert segmenter.flush() == []


def test_app_dispatches_shape_and_keeps_shake(tmp_path):
    shakes: list = []
    shapes: list = []
    app = App(
        db_path=tmp_path / "events.db",
        on_shake=shakes.append,
        on_shape=lambda name, score, segment: shapes.append((name, score, len(segment))),
    )
    try:
        stroke = shake_events(start_ms=1_000_000)
        for event in stroke:
            app.inbox.put(event)
        assert app.drain_once() == len(stroke)
        assert len(shakes) == 1
        assert shapes == []

        circle = circle_events(start_ms=stroke[-1].ts_ms + SHAPE_IDLE_MS + 100)
        for event in circle:
            app.inbox.put(event)
        assert app.drain_once() == len(circle)
        assert len(shakes) == 1
        app.flush_shapes()
        assert len(shapes) == 1
        name, score, size = shapes[0]
        assert name == "circle"
        assert score >= SHAPE_SCORE_THRESHOLD
        assert size == len(circle)
        assert app.store.count() == len(stroke) + len(circle)
    finally:
        app.close()
