from __future__ import annotations

from collections.abc import Sequence

from .events import MouseEvent

# Live-mouse tune: a deliberate wiggle is 2+ full cycles inside ~1s at
# well above 400 px/s; drift and aim correction stay below that floor.
WINDOW_MS = 1000
MIN_ZERO_CROSSINGS = 4
MIN_SPEED_PX_S = 400.0
COOLDOWN_MS = 1500
MIN_SAMPLES = 8
MIN_X_RANGE_PX = 40


class ShakeDetector:
    """Counts x-velocity sign flips inside a trailing window. Consumer thread only."""

    def __init__(
        self,
        window_ms: int = WINDOW_MS,
        min_crossings: int = MIN_ZERO_CROSSINGS,
        min_speed_px_s: float = MIN_SPEED_PX_S,
        cooldown_ms: int = COOLDOWN_MS,
        min_samples: int = MIN_SAMPLES,
    ) -> None:
        self.window_ms = window_ms
        self.min_crossings = min_crossings
        self.min_speed_px_s = min_speed_px_s
        self.cooldown_ms = cooldown_ms
        self.min_samples = min_samples
        self._last_fire_ms: int | None = None

    @property
    def last_fire_ms(self) -> int | None:
        return self._last_fire_ms

    def check(self, events: Sequence[MouseEvent]) -> bool:
        if len(events) < self.min_samples:
            return False
        now = events[-1].ts_ms
        if self._last_fire_ms is not None and now - self._last_fire_ms < self.cooldown_ms:
            return False
        window = [e for e in events if now - e.ts_ms <= self.window_ms]
        if len(window) < self.min_samples:
            return False
        xs = [e.x for e in window]
        if max(xs) - min(xs) < MIN_X_RANGE_PX:
            return False
        crossings = 0
        prev_sign = 0
        for i in range(1, len(window)):
            dt_s = (window[i].ts_ms - window[i - 1].ts_ms) / 1000.0
            if dt_s <= 0:
                continue
            vx = (window[i].x - window[i - 1].x) / dt_s
            if abs(vx) < self.min_speed_px_s:
                continue
            sign = 1 if vx > 0 else -1
            if prev_sign != 0 and sign != prev_sign:
                crossings += 1
            prev_sign = sign
        if crossings >= self.min_crossings:
            self._last_fire_ms = now
            return True
        return False
