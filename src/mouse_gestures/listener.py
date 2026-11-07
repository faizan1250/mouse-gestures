from __future__ import annotations

import queue

from pynput import mouse

from .events import MouseEvent, encode_buttons, now_ms


class MouseListener:
    """pynput listener. Callbacks do queue.put only — never deque/DB/detect."""

    def __init__(self, outbox: queue.Queue[MouseEvent]) -> None:
        self._outbox = outbox
        self._pressed: set[str] = set()
        self._listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )

    def _buttons(self) -> str:
        return encode_buttons(
            left="left" in self._pressed,
            right="right" in self._pressed,
            middle="middle" in self._pressed,
        )

    def _on_move(self, x: float, y: float) -> None:
        self._outbox.put(MouseEvent(ts_ms=now_ms(), x=int(x), y=int(y), buttons=self._buttons()))

    def _on_click(self, x: float, y: float, button: mouse.Button, pressed: bool) -> None:
        name = button.name if isinstance(button, mouse.Button) else str(button)
        if pressed:
            self._pressed.add(name)
        else:
            self._pressed.discard(name)
        self._outbox.put(MouseEvent(ts_ms=now_ms(), x=int(x), y=int(y), buttons=self._buttons()))

    def _on_scroll(self, x: float, y: float, dx: float, dy: float) -> None:
        self._outbox.put(MouseEvent(ts_ms=now_ms(), x=int(x), y=int(y), buttons=self._buttons()))

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()

    def join(self, timeout: float | None = None) -> None:
        self._listener.join(timeout)
