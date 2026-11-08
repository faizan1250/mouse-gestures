from __future__ import annotations

import argparse
import html
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

MAX_EVENTS = 20_000
WIDTH = 800
HEIGHT = 600
PAD = 24
GRID_COLS = 32
GRID_ROWS = 24

EventRow = tuple[int, int, int]  # (ts_ms, x, y)


def open_readonly(db_path: str | Path) -> sqlite3.Connection:
    """Open an existing DB read-only. Missing file raises; nothing is created."""
    quoted = quote(str(Path(db_path).resolve()), safe="/:\\")
    uri = f"file:{quoted}?mode=ro"
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


def build_grid(
    scaled: list[tuple[float, float]],
    cols: int = GRID_COLS,
    rows: int = GRID_ROWS,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> list[list[int]]:
    """Bin canvas points into a rows x cols hit-count grid. Edge points clamp inward."""
    if cols <= 0 or rows <= 0:
        raise ValueError(f"grid must be positive, got {cols}x{rows}")
    if width <= 0 or height <= 0:
        raise ValueError(f"canvas must be positive, got {width}x{height}")
    grid = [[0] * cols for _ in range(rows)]
    for sx, sy in scaled:
        c = min(int(sx / width * cols), cols - 1)
        r = min(int(sy / height * rows), rows - 1)
        grid[max(r, 0)][max(c, 0)] += 1
    return grid


def _heatmap_rects(grid: list[list[int]], width: int, height: int) -> str:
    rows, cols = len(grid), len(grid[0])
    peak = max(max(row) for row in grid)
    if peak == 0:
        return ""
    cell_w, cell_h = width / cols, height / rows
    parts = []
    for r in range(rows):
        for c in range(cols):
            n = grid[r][c]
            if n == 0:
                continue
            opacity = 0.15 + 0.85 * (n / peak)
            parts.append(
                f'<rect x="{c * cell_w:.1f}" y="{r * cell_h:.1f}" '
                f'width="{cell_w:.1f}" height="{cell_h:.1f}" '
                f'fill="red" opacity="{opacity:.2f}"/>'
            )
    return "".join(parts)


def _trail_polyline(scaled: list[tuple[float, float]]) -> str:
    if not scaled:
        return ""
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in scaled)
    return f'<polyline points="{pts}" fill="none" stroke="blue" stroke-width="2"/>'


def render_html(
    events: list[EventRow],
    width: int = WIDTH,
    height: int = HEIGHT,
    cols: int = GRID_COLS,
    rows: int = GRID_ROWS,
    db_label: str = "",
) -> str:
    """Self-contained page: heatmap rects under a trail polyline. No external refs."""
    scaled = scale_points(events, width, height)
    grid = build_grid(scaled, cols, rows, width, height)
    if events:
        body = (
            f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f"{_heatmap_rects(grid, width, height)}{_trail_polyline(scaled)}</svg>"
            f"<p>{len(events)} points, {events[0][0]}..{events[-1][0]} ms</p>"
        )
    else:
        body = (
            f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"></svg>'
            "<p>No events in range.</p>"
        )
    label = f" — {html.escape(db_label)}" if db_label else ""
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<title>mouse trail{label}</title>"
        "<style>body{font-family:sans-serif}svg{border:1px solid #999}</style>"
        f"</head><body><h1>mouse trail{label}</h1>{body}</body></html>"
    )


def write_html(out_path: str | Path, page: str) -> Path:
    """Write the page locally (parents created). The only write the viewer performs."""
    out = Path(out_path)
    if out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    """CLI: read the store read-only, write a self-contained .html file locally."""
    parser = argparse.ArgumentParser(description="Local-only mouse trail/heatmap viewer.")
    parser.add_argument("--db", default="mouse_events.db")
    parser.add_argument("--out", default="trail.html")
    parser.add_argument("--since", type=int, default=0)
    parser.add_argument("--until", type=int, default=None)
    parser.add_argument("--limit", type=int, default=MAX_EVENTS)
    args = parser.parse_args(argv)
    try:
        events = load_events(args.db, args.since, args.until, args.limit)
    except ValueError as exc:
        print(f"viewer: invalid limit {args.limit}: {exc}", file=sys.stderr)
        return 1
    except sqlite3.Error as exc:
        print(f"viewer: cannot read {args.db}: {exc}", file=sys.stderr)
        return 1
    try:
        write_html(args.out, render_html(events, db_label=str(args.db)))
    except OSError as exc:
        print(f"viewer: cannot write {args.out}: {exc}", file=sys.stderr)
        return 1
    print(f"viewer: {len(events)} points -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
