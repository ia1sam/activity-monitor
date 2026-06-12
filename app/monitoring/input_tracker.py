from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

from pynput import keyboard, mouse


@dataclass(frozen=True)
class InputCounters:
    keyboard_count: int
    mouse_moves: int
    mouse_clicks: int


class InputTracker:
    def __init__(self, move_threshold_px: int = 25) -> None:
        self._move_threshold_px = move_threshold_px
        self._lock = threading.Lock()
        self._keyboard_count = 0
        self._mouse_moves = 0
        self._mouse_clicks = 0
        self._pressed_keys: set[object] = set()
        self._last_pos: tuple[int, int] | None = None
        self._accumulated_distance = 0.0
        self._last_input_time = time.time()
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        keyboard.Listener(on_press=self._on_press, on_release=self._on_release).start()
        mouse.Listener(on_move=self._on_move, on_click=self._on_click).start()
        self._started = True

    def is_idle(self, idle_threshold_sec: int) -> bool:
        return time.time() - self._last_input_time > idle_threshold_sec

    def counters(self) -> InputCounters:
        with self._lock:
            return InputCounters(
                keyboard_count=self._keyboard_count,
                mouse_moves=self._mouse_moves,
                mouse_clicks=self._mouse_clicks,
            )

    def reset(self) -> None:
        with self._lock:
            self._keyboard_count = 0
            self._mouse_moves = 0
            self._mouse_clicks = 0
            self._accumulated_distance = 0.0
            self._last_pos = None

    def _mark_input(self) -> None:
        self._last_input_time = time.time()

    def _on_press(self, key: object) -> None:
        with self._lock:
            if key not in self._pressed_keys:
                self._pressed_keys.add(key)
                self._keyboard_count += 1
        self._mark_input()

    def _on_release(self, key: object) -> None:
        with self._lock:
            self._pressed_keys.discard(key)

    def _on_move(self, x: int, y: int) -> None:
        with self._lock:
            if self._last_pos is None:
                self._last_pos = (x, y)
                return

            dx = x - self._last_pos[0]
            dy = y - self._last_pos[1]
            self._accumulated_distance += math.sqrt(dx * dx + dy * dy)

            if self._accumulated_distance > self._move_threshold_px:
                self._mouse_moves += 1
                self._accumulated_distance = 0.0

            self._last_pos = (x, y)
        self._mark_input()

    def _on_click(self, x: int, y: int, button: object, pressed: bool) -> None:
        if pressed:
            with self._lock:
                self._mouse_clicks += 1
        self._mark_input()
