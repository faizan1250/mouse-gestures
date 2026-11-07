from __future__ import annotations

import time
from dataclasses import dataclass

BUTTON_NONE = "none"
BUTTON_LEFT = "left"
BUTTON_RIGHT = "right"
BUTTON_MIDDLE = "middle"


@dataclass(frozen=True, slots=True)
class MouseEvent:
    ts_ms: int
    x: int
    y: int
    buttons: str = BUTTON_NONE


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def encode_buttons(left: bool = False, right: bool = False, middle: bool = False) -> str:
    parts: list[str] = []
    if left:
        parts.append(BUTTON_LEFT)
    if right:
        parts.append(BUTTON_RIGHT)
    if middle:
        parts.append(BUTTON_MIDDLE)
    return "|".join(parts) if parts else BUTTON_NONE
