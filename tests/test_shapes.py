import math

import pytest
from conftest import circle_events, delete_events, drift_events, triangle_events
from mouse_gestures.shapes import (
    SHAPE_SCORE_THRESHOLD,
    SHAPE_SQUARE_SIZE,
    RESAMPLE_N,
    TEMPLATES,
    ShapeRecognizer,
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
