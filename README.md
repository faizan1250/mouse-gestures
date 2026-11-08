# mouse-gestures — slice 1

Local Windows shake-to-act: shake the mouse and the app fires a callback
(e.g. `print("shake detected")` — wired as callback injection, no toast dependency).

## What

- Windows `pynput` mouse listener (trivial `queue.put` only) → `queue.Queue` →
  consumer loop owning deque ring + shake detector (x-velocity zero-crossing) +
  SQLite WAL logger + realtime callback.
- Example: run `python -m mouse_gestures.app`, shake side-to-side, see `shake detected`.

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
- Latency: 50ms drain budget (`DRAIN_TIMEOUT_S=0.05`) targeting sub-100ms
  end-to-end — a budget, not a hard SLA.

## Install (Windows, Python >= 3.10)

```bash
pip install -e ".[test]"
python -m mouse_gestures.app   # prints on shake
pytest -q
```

- CI: `windows-latest`, Python 3.10, `pip install ".[test]"`, `pytest -q`.

## Tests

- `tests/test_detector.py` (9) — window/crossings/speed/cooldown/x-range/sample-gate behavior.
- `tests/test_store.py` (5) — schema/index, batching, fetch roundtrip, close idempotency, retention prune.
- `tests/test_app.py` (5) — `drain_once` dispatch, callback contract, ring windowing, drain-path prune.

## Privacy

- Local-only: no network calls, no telemetry, no secrets in repo.
- DB file chmod `0600` (best-effort on Windows).
- `*.db` / WAL / SHM are gitignored — never committed.
- Wipe: delete `mouse_events.db*` to remove all recorded data.

## Roadmap

- Slice 1 (done): listener → queue → ring + detector + WAL store + callback.
- Slice 2 (done): 7-day default retention auto-prune via drain-path `prune_older_than`.
- Slice 5 (done): live-mouse retune of detector window/crossings/speed floor.

## Invariants

- SQLite connection lives only on the consumer thread.
- `buttons` TEXT is `none` or pipe-joined subset of `left|right|middle`.

## Layout

- `src/mouse_gestures/events.py` — `MouseEvent(ts_ms,x,y,buttons)`
- `src/mouse_gestures/listener.py` — pynput, put-only
- `src/mouse_gestures/ring.py` — deque ring, consumer-owned
- `src/mouse_gestures/detector.py` — window/crossings/speed/cooldown constants (live-mouse tuned)
- `src/mouse_gestures/store.py` — `mouse_events(ts_ms,x,y,buttons)`, index on `ts_ms`, WAL+NORMAL, batched commits, 7-day prune
- `src/mouse_gestures/app.py` — drain loop + dispatch
