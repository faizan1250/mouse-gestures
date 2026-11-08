import hashlib
import sqlite3

import pytest
from conftest import drift_events, shake_events

from mouse_gestures import viewer
from mouse_gestures.store import EventStore


def _seed(db_path, events):
    store = EventStore(db_path)
    try:
        for event in events:
            store.append(event)
        store.flush()
    finally:
        store.close()


def _rows(events):
    return [(e.ts_ms, e.x, e.y) for e in events]


def test_loads_seeded_rows_readonly(tmp_path):
    db = tmp_path / "events.db"
    events = shake_events()
    _seed(db, events)
    rows = viewer.load_events(db)
    assert len(rows) == len(events)
    assert rows[0] == (events[0].ts_ms, events[0].x, events[0].y)


def test_missing_db_raises_without_creating(tmp_path):
    db = tmp_path / "nope.db"
    with pytest.raises(sqlite3.Error):
        viewer.load_events(db)
    assert not db.exists()


def test_empty_db_renders_placeholder(tmp_path):
    db = tmp_path / "events.db"
    _seed(db, [])
    assert viewer.load_events(db) == []
    page = viewer.render_html([])
    assert "<svg" in page
    assert "No events" in page


def test_range_filter_and_limit(tmp_path):
    db = tmp_path / "events.db"
    events = shake_events()
    _seed(db, events)
    lo, hi = events[0].ts_ms + 200, events[0].ts_ms + 400
    rows = viewer.load_events(db, since_ms=lo, until_ms=hi)
    assert 0 < len(rows) < len(events)
    assert all(lo <= r[0] <= hi for r in rows)
    assert len(viewer.load_events(db, limit=5)) == 5


def test_scaling_fits_canvas_and_grid_counts():
    rows = _rows(shake_events())
    scaled = viewer.scale_points(rows)
    assert all(0.0 <= x <= viewer.WIDTH and 0.0 <= y <= viewer.HEIGHT for x, y in scaled)
    grid = viewer.build_grid(scaled)
    assert len(grid) == viewer.GRID_ROWS and all(len(r) == viewer.GRID_COLS for r in grid)
    assert sum(map(sum, grid)) == len(rows)


def test_single_point_centers():
    scaled = viewer.scale_points([(1_000_000, 321, 123)])
    assert scaled == [(viewer.WIDTH / 2.0, viewer.HEIGHT / 2.0)]


def test_read_leaves_db_untouched(tmp_path):
    db = tmp_path / "events.db"
    events = drift_events()
    _seed(db, events)
    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    mtime = db.stat().st_mtime_ns
    viewer.render_html(viewer.load_events(db))
    assert db.stat().st_mtime_ns == mtime
    assert hashlib.sha256(db.read_bytes()).hexdigest() == digest
    assert len(viewer.load_events(db)) == len(events)


def test_html_self_contained():
    page = viewer.render_html(_rows(shake_events()), db_label="events.db")
    assert "<polyline" in page
    assert "<rect" in page
    lowered = page.lower()
    assert "http://" not in lowered and "https://" not in lowered
    assert "src=" not in lowered and "href=" not in lowered and "<script" not in lowered


def test_cli_writes_html_locally(tmp_path):
    db = tmp_path / "events.db"
    out = tmp_path / "trail.html"
    _seed(db, shake_events())
    assert viewer.main(["--db", str(db), "--out", str(out)]) == 0
    assert "<svg" in out.read_text(encoding="utf-8")
