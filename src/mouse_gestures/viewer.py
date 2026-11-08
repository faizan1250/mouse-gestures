from __future__ import annotations

import sqlite3
from pathlib import Path

MAX_EVENTS = 20_000
WIDTH = 800
HEIGHT = 600
PAD = 24
GRID_COLS = 32
GRID_ROWS = 24

EventRow = tuple[int, int, int]  # (ts_ms, x, y)


def open_readonly(db_path: str | Path) -> sqlite3.Connection:
    """Open an existing DB read-only. Missing file raises; nothing is created."""
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=True)
    try:
        conn.execute("PRAGMA query_only=ON;")
    except Exception:
        conn.close()
        raise
    return conn


def fetch_events(
    conn: sqlite3.Connection,
    since_ms: int = 0,
    until_ms: int | None = None,
    limit: int = MAX_EVENTS,
) -> list[EventRow]:
    """Bounded range scan over mouse_events, oldest first. Parameterized; no SELECT *."""
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    query = "SELECT ts_ms, x, y FROM mouse_events WHERE ts_ms >= ?"
    params: list[int] = [since_ms]
    if until_ms is not None:
        query += " AND ts_ms <= ?"
        params.append(until_ms)
    query += " ORDER BY ts_ms LIMIT ?"
    params.append(limit)
    return [(r[0], r[1], r[2]) for r in conn.execute(query, params).fetchall()]


def load_events(
    db_path: str | Path,
    since_ms: int = 0,
    until_ms: int | None = None,
    limit: int = MAX_EVENTS,
) -> list[EventRow]:
    """Seed-free read path: open read-only, fetch, close. Never touches EventStore."""
    conn = open_readonly(db_path)
    try:
        return fetch_events(conn, since_ms, until_ms, limit)
    finally:
        conn.close()


def data_bounds(events: list[EventRow]) -> tuple[float, float, float, float]:
    """Data-space (min_x, min_y, max_x, max_y); unit fallback keeps empty renders valid."""
    if not events:
        return (0.0, 0.0, 1.0, 1.0)
    xs = [e[1] for e in events]
    ys = [e[2] for e in events]
    return (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))


def scale_points(
    events: list[EventRow],
    width: int = WIDTH,
    height: int = HEIGHT,
    pad: int = PAD,
) -> list[tuple[float, float]]:
    """Fit data bounds into the canvas with uniform scale, centered. Zero-span safe."""
    if width <= 0 or height <= 0:
        raise ValueError(f"canvas must be positive, got {width}x{height}")
    if pad < 0 or 2 * pad >= min(width, height):
        raise ValueError(f"pad {pad} leaves no drawable area in {width}x{height}")
    if not events:
        return []
    min_x, min_y, max_x, max_y = data_bounds(events)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    scale = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)
    cx, cy = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
    return (
        [(width / 2.0 + (e[1] - cx) * scale, height / 2.0 + (e[2] - cy) * scale) for e in events]
    )
