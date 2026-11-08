# mouse-gestures

Local Windows mouse gestures: shake the mouse and the app prints
`shake detected`; draw a circle/triangle/delete and it prints
`shape: <name> (<score>, <n> pts)`. Recorded trails can be rendered to a
self-contained local HTML heatmap via the viewer.

## What

- Windows `pynput` mouse listener (trivial `queue.put` only) → `queue.Queue` →
  consumer loop owning deque ring + shake detector + shape segmenter/recognizer +
  SQLite WAL logger + realtime callbacks.
- Example: run `python -m mouse_gestures.app`, shake side-to-side, see `shake detected`;
  pause 800ms between strokes, draw a circle, see `shape: circle (...)`.
- Example: run `python -m mouse_gestures.viewer --db mouse_events.db --out trail.html`,
  open `trail.html` in a browser for the trail heatmap.

## How it works

- Listener thread does `put` only — never touches deque / DB / detector / callback.
- Consumer `drain_once` drains the inbox, appends to ring, persists, runs detection.
- Ring: `deque` with `maxlen=512` (`RING_MAXLEN`), consumer-owned.
- Detector (x-velocity zero-crossings in trailing window, live-mouse tuned —
  a deliberate wiggle is 2+ full cycles inside ~1s well above 400 px/s):
  `WINDOW_MS=1000`, `MIN_ZERO_CROSSINGS=4`, `MIN_SPEED_PX_S=400`,
  `COOLDOWN_MS=1500`, `MIN_SAMPLES=8`, `MIN_X_RANGE_PX=40`.
- Store: table `mouse_events(ts_ms,x,y,buttons)`, index on `ts_ms`,
  `WAL` + `NORMAL`, batched commits (`BATCH_SIZE=100`),
  7-day auto-prune on drain (`prune_older_than`, cutoff = newest event − `RETENTION_MS`).
- Shapes: idle-gap segmenter (`SHAPE_IDLE_MS=800`, drops fragments < `MIN_SHAPE_POINTS=16`)
  → pure-stdlib $1 recognizer (`circle`/`triangle`/`delete`, `SHAPE_SCORE_THRESHOLD=0.80`);
  trailing segment flushed on teardown.
- Viewer: opens the DB read-only (`mode=ro` + `query_only`), bounded range scan
  (`--since`/`--until`/`--limit`, `MAX_EVENTS=20000`), uniform-scale polyline +
  32×24 hit-grid heatmap, single local `.html` write (the only write it performs).
- Latency: 50ms drain budget (`DRAIN_TIMEOUT_S=0.05`) targeting sub-100ms
  end-to-end — a budget, not a hard SLA.

## Install & run (Windows, Python >= 3.10)

```bash
pip install -e ".[test]"
python -m mouse_gestures.app   # prints "shake detected" / "shape: <name> ..."
pytest -q
```

Render the recorded trail after a run:

```bash
python -m mouse_gestures.viewer --db mouse_events.db --out trail.html
```

- Entry points are `python -m` modules (no console-script wrappers).
- CI: `windows-latest`, Python 3.10, `pip install ".[test]"`, `pytest -q`.

## Tests

- `tests/test_detector.py` (9) — window/crossings/speed/cooldown/x-range/sample-gate behavior.
- `tests/test_store.py` (5) — schema/index, batching, fetch roundtrip, close idempotency, retention prune.
- `tests/test_app.py` (5) — `drain_once` dispatch, callback contract, ring windowing, drain-path prune.
- `tests/test_shapes.py` (17) — resample/normalize/rotation invariance, template match + rejects, idle segmentation, app shape dispatch.
- `tests/test_viewer.py` (13) — read-only load, missing-DB guard, range/limit, scaling/grid, self-contained HTML, CLI write/fail paths.

## Privacy

- Local-only: no network calls, no telemetry, no secrets in repo.
- Viewer opens the DB read-only and never touches `EventStore`; its only write
  is the local output `.html`.
- DB file chmod `0600` (best-effort on Windows).
- `*.db` / WAL / SHM are gitignored — never committed.
- Wipe: delete `mouse_events.db*` to remove all recorded data.

## Roadmap

- Slice 1 (done): listener → queue → ring + detector + WAL store + callback.
- Slice 2 (done): 7-day default retention auto-prune via drain-path `prune_older_than`.
- Slice 3 (done): $1 shape recognizer (circle/triangle/delete) + idle-gap segmenter wired into `App`.
- Slice 4 (done): read-only viewer CLI (`--db`/`--out`/`--since`/`--until`/`--limit`) rendering local trail heatmap HTML.
- Slice 5 (done): live-mouse retune of detector window/crossings/speed floor.
- Slice 6 (this): packaging polish + README demo flow.

## Invariants

- SQLite connection lives only on the consumer thread.
- `buttons` TEXT is `none` or pipe-joined subset of `left|right|middle`.

## Layout

- `src/mouse_gestures/events.py` — `MouseEvent(ts_ms,x,y,buttons)`
- `src/mouse_gestures/listener.py` — pynput, put-only
- `src/mouse_gestures/ring.py` — deque ring, consumer-owned
- `src/mouse_gestures/detector.py` — window/crossings/speed/cooldown constants (live-mouse tuned)
- `src/mouse_gestures/store.py` — `mouse_events(ts_ms,x,y,buttons)`, index on `ts_ms`, WAL+NORMAL, batched commits, 7-day prune
- `src/mouse_gestures/shapes.py` — $1 recognizer + idle-gap segmenter (consumer thread only)
- `src/mouse_gestures/viewer.py` — read-only loader + heatmap renderer + `--db/--out` CLI
- `src/mouse_gestures/app.py` — drain loop + dispatch
