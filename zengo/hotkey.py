"""Global "press Ctrl+C twice" detector (DeepL-style trigger)."""
from __future__ import annotations

import time
from typing import Callable

from pynput import keyboard

VK_C = 0x43


class DoubleCopyListener:
    def __init__(self, on_trigger: Callable[[], None], window_ms: int = 500):
        self.on_trigger = on_trigger
        self.window = window_ms / 1000
        self._ctrl = set()
        self._c_down = False
        self._last = 0.0
        self._listener = keyboard.Listener(on_press=self._press, on_release=self._release)

    def start(self):
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        self._listener.stop()

    @staticmethod
    def _is_c(key) -> bool:
        vk = getattr(key, "vk", None)
        ch = getattr(key, "char", None)
        return vk == VK_C or ch in ("c", "C", "\x03")

    def _press(self, key):
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self._ctrl.add(key)
            return
        if not self._is_c(key):
            self._last = 0.0  # any other key breaks the sequence
            return
        if not self._ctrl or self._c_down:  # ignore auto-repeat while held
            return
        self._c_down = True
        now = time.monotonic()
        if now - self._last <= self.window:
            self._last = 0.0
            self.on_trigger()
        else:
            self._last = now

    def _release(self, key):
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self._ctrl.discard(key)
        elif self._is_c(key):
            self._c_down = False
