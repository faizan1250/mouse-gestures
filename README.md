# mouse-gestures — slice 1

Windows `pynput` mouse listener (trivial `queue.put` only) → `queue.Queue` →
consumer loop owning deque ring + shake detector (x-velocity zero-crossing) +
SQLite WAL logger + realtime callback.

## Invariants

- Listener thread never touches deque / DB / detector / callback.
- SQLite connection lives only on the consumer thread.
- `buttons` TEXT is `none` or pipe-joined subset of `left|right|middle`.
- Callback-injection only; example uses `print` (no toast dependency).
- Local-only, no network. DB file chmod 0600 (best-effort on Windows).
- No auto-prune in slice 1. TODO(slice2): 7-day default retention prune.

## Run

```bash
pip install -e ".[test]"
python -m mouse_gestures.app   # prints on shake
pytest -q
```

## Layout

- `src/mouse_gestures/events.py` — `MouseEvent(ts_ms,x,y,buttons)`
- `src/mouse_gestures/listener.py` — pynput, put-only
- `src/mouse_gestures/ring.py` — deque ring, consumer-owned
- `src/mouse_gestures/detector.py` — window/crossings/speed/cooldown constants
- `src/mouse_gestures/store.py` — `mouse_events(ts_ms,x,y,buttons)`, index on `ts_ms`, WAL+NORMAL, batched commits
- `src/mouse_gestures/app.py` — drain loop + dispatch
