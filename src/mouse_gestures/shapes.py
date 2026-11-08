from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .events import MouseEvent

RESAMPLE_N = 64
SHAPE_SQUARE_SIZE = 250.0
SHAPE_ANGLE_RANGE_RAD = math.radians(45.0)
SHAPE_ANGLE_PRECISION_RAD = math.radians(2.0)
SHAPE_SCORE_THRESHOLD = 0.80
SHAPE_IDLE_MS = 800
MIN_SHAPE_POINTS = 16
GOLDEN_RATIO = (math.sqrt(5.0) - 1.0) / 2.0

Point = tuple[float, float]

CIRCLE_ANCHORS: tuple[Point, ...] = tuple(
    (0.5 + 0.5 * math.cos(2.0 * math.pi * i / 32.0), 0.5 + 0.5 * math.sin(2.0 * math.pi * i / 32.0))
    for i in range(33)
)
TRIANGLE_ANCHORS: tuple[Point, ...] = ((0.0, 1.0), (1.0, 1.0), (0.5, 0.0), (0.0, 1.0))
DELETE_ANCHORS: tuple[Point, ...] = ((0.0, 0.0), (1.0, 0.0), (0.0, 0.5), (1.0, 0.5), (0.0, 1.0), (1.0, 1.0))


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _path_length(points: Sequence[Point]) -> float:
    return sum(_dist(points[i - 1], points[i]) for i in range(1, len(points)))


def resample(points: Sequence[Point], n: int = RESAMPLE_N) -> list[Point]:
    """Resample a stroke to n evenly spaced points along its path."""
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    pts = [(float(x), float(y)) for x, y in points]
    if not pts:
        raise ValueError("resample requires at least one point")
    if len(pts) == 1:
        return [pts[0]] * n
    total = _path_length(pts)
    if total == 0.0:
        return [pts[0]] * n
    interval = total / (n - 1)
    out = [pts[0]]
    prev = pts[0]
    acc = 0.0
    i = 1
    while i < len(pts) and len(out) < n:
        d = _dist(prev, pts[i])
        if d <= 0.0:
            i += 1
            continue
        if acc + d >= interval:
            t = (interval - acc) / d
            prev = (prev[0] + t * (pts[i][0] - prev[0]), prev[1] + t * (pts[i][1] - prev[1]))
            out.append(prev)
            acc = 0.0
        else:
            acc += d
            prev = pts[i]
            i += 1
    while len(out) < n:
        out.append(pts[-1])
    return out


def centroid(points: Sequence[Point]) -> Point:
    if not points:
        raise ValueError("centroid requires at least one point")
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def indicative_angle(points: Sequence[Point]) -> float:
    cx, cy = centroid(points)
    return math.atan2(cy - points[0][1], cx - points[0][0])


def rotate_points(points: Sequence[Point], angle_rad: float, center: Point = (0.0, 0.0)) -> list[Point]:
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    cx, cy = center
    return [
        (cx + (x - cx) * cos_a - (y - cy) * sin_a, cy + (x - cx) * sin_a + (y - cy) * cos_a)
        for x, y in points
    ]


def rotate_to_zero(points: Sequence[Point]) -> list[Point]:
    return rotate_points(points, -indicative_angle(points), centroid(points))


def scale_to_square(points: Sequence[Point], size: float = SHAPE_SQUARE_SIZE) -> list[Point]:
    if size <= 0.0:
        raise ValueError(f"size must be positive, got {size}")
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    sx = size / width if width > 0.0 else 1.0
    sy = size / height if height > 0.0 else 1.0
    return [(x * sx, y * sy) for x, y in points]


def translate_to_origin(points: Sequence[Point]) -> list[Point]:
    cx, cy = centroid(points)
    return [(x - cx, y - cy) for x, y in points]


def normalize_points(
    points: Sequence[Point], n: int = RESAMPLE_N, size: float = SHAPE_SQUARE_SIZE
) -> list[Point]:
    return translate_to_origin(scale_to_square(rotate_to_zero(resample(points, n)), size))


def path_distance(a: Sequence[Point], b: Sequence[Point]) -> float:
    if not a or not b:
        raise ValueError("path_distance requires non-empty point lists")
    if len(a) != len(b):
        raise ValueError(f"length mismatch: {len(a)} != {len(b)}")
    return sum(_dist(p, q) for p, q in zip(a, b)) / len(a)


def distance_at_angle(candidate: Sequence[Point], template: Sequence[Point], angle_rad: float) -> float:
    return path_distance(rotate_points(candidate, angle_rad), template)


def distance_at_best_angle(
    candidate: Sequence[Point],
    template: Sequence[Point],
    angle_range: float = SHAPE_ANGLE_RANGE_RAD,
    precision: float = SHAPE_ANGLE_PRECISION_RAD,
) -> float:
    a, b = -angle_range, angle_range
    x1 = GOLDEN_RATIO * a + (1.0 - GOLDEN_RATIO) * b
    f1 = distance_at_angle(candidate, template, x1)
    x2 = (1.0 - GOLDEN_RATIO) * a + GOLDEN_RATIO * b
    f2 = distance_at_angle(candidate, template, x2)
    while abs(b - a) > precision:
        if f1 < f2:
            b, x2, f2 = x2, x1, f1
            x1 = GOLDEN_RATIO * a + (1.0 - GOLDEN_RATIO) * b
            f1 = distance_at_angle(candidate, template, x1)
        else:
            a, x1, f1 = x1, x2, f2
            x2 = (1.0 - GOLDEN_RATIO) * a + GOLDEN_RATIO * b
            f2 = distance_at_angle(candidate, template, x2)
    return min(f1, f2)


def _preprocess(anchors: Sequence[Point]) -> list[Point]:
    return normalize_points(anchors)


TEMPLATES: dict[str, list[Point]] = {
    "circle": _preprocess(CIRCLE_ANCHORS),
    "triangle": _preprocess(TRIANGLE_ANCHORS),
    "delete": _preprocess(DELETE_ANCHORS),
}


def half_diagonal(size: float = SHAPE_SQUARE_SIZE) -> float:
    return 0.5 * math.hypot(size, size)


def recognize_points(
    points: Sequence[Point],
    templates: Mapping[str, Sequence[Point]] = TEMPLATES,
    threshold: float = SHAPE_SCORE_THRESHOLD,
) -> tuple[str | None, float]:
    """Match a stroke against templates. Returns (name, score); name is None below threshold."""
    if len(points) == 0:
        return None, 0.0
    candidate = normalize_points(points)
    best_name: str | None = None
    best_dist = math.inf
    for name, template in templates.items():
        d = distance_at_best_angle(candidate, template)
        if d < best_dist:
            best_dist, best_name = d, name
    if best_name is None:
        return None, 0.0
    score = 1.0 - best_dist / half_diagonal()
    return (best_name, score) if score >= threshold else (None, score)


class ShapeSegmenter:
    """Idle-gap splitter over drained batches. Consumer thread only.

    Feed each drained batch; segments followed by an idle gap come back as
    complete. The trailing segment stays pending until a later gap or flush().
    Fragments below min_points are dropped.
    """

    def __init__(
        self,
        idle_ms: int = SHAPE_IDLE_MS,
        min_points: int = MIN_SHAPE_POINTS,
    ) -> None:
        self.idle_ms = idle_ms
        self.min_points = min_points
        self._pending: list[MouseEvent] = []

    @property
    def pending(self) -> list[MouseEvent]:
        return list(self._pending)

    def feed(self, events: Sequence[MouseEvent]) -> list[list[MouseEvent]]:
        completed: list[list[MouseEvent]] = []
        for event in events:
            if self._pending and event.ts_ms - self._pending[-1].ts_ms > self.idle_ms:
                if len(self._pending) >= self.min_points:
                    completed.append(list(self._pending))
                self._pending = []
            self._pending.append(event)
        return completed

    def flush(self) -> list[MouseEvent]:
        segment, self._pending = self._pending, []
        return segment if len(segment) >= self.min_points else []


class ShapeRecognizer:
    """$1 stroke recognizer. Pure and stateless; consumer thread only."""

    def __init__(
        self,
        templates: Mapping[str, Sequence[Point]] | None = None,
        threshold: float = SHAPE_SCORE_THRESHOLD,
    ) -> None:
        self.templates = dict(TEMPLATES if templates is None else templates)
        self.threshold = threshold

    def recognize_points(self, points: Sequence[Point]) -> tuple[str | None, float]:
        return recognize_points(points, self.templates, self.threshold)

    def recognize_events(self, events: Sequence[MouseEvent]) -> tuple[str | None, float]:
        if len(events) == 0:
            return None, 0.0
        return self.recognize_points([(float(e.x), float(e.y)) for e in events])
