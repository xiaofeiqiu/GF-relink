import pydirectinput
import win32api
import win32con
import time
import threading
import logging
from abc import ABC, abstractmethod

pydirectinput.FAILSAFE = False

log = logging.getLogger("sender")


class InputSender(ABC):
    @abstractmethod
    def press(self, key: str) -> None:
        pass

    @abstractmethod
    def hold(self, key: str, duration: float, hold_while: threading.Event | None = None) -> None:
        pass

    @abstractmethod
    def click_left(self) -> None:
        pass

    @abstractmethod
    def click_middle(self) -> None:
        pass

    @abstractmethod
    def release_all(self) -> None:
        pass


class DirectInputSender(InputSender):
    def __init__(self):
        self._held_keys: set[str] = set()
        self._lock = threading.Lock()

    def press(self, key: str) -> None:
        pydirectinput.press(key)

    def hold(self, key: str, duration: float, hold_while: threading.Event | None = None) -> None:
        with self._lock:
            self._held_keys.add(key)
        try:
            pydirectinput.keyDown(key)
            if hold_while is None:
                time.sleep(duration)
            else:
                end = time.monotonic() + duration
                while time.monotonic() < end and hold_while.is_set():
                    time.sleep(0.05)
        finally:
            pydirectinput.keyUp(key)
            with self._lock:
                self._held_keys.discard(key)

    def click_left(self) -> None:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def click_middle(self) -> None:
        win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)

    def release_all(self) -> None:
        with self._lock:
            keys = list(self._held_keys)
            self._held_keys.clear()
        for key in keys:
            try:
                pydirectinput.keyUp(key)
                log.info(f"Released {key}")
            except Exception as e:
                log.warning(f"Failed to release {key}: {e}")
