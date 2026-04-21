import mss
import numpy as np
import win32gui
import threading
from abc import ABC, abstractmethod


class ScreenCapturer(ABC):
    @abstractmethod
    def capture(self, hwnd: int) -> np.ndarray:
        pass

    def close(self) -> None:
        pass

    def close_current_thread(self) -> None:
        pass


class MssScreenCapturer(ScreenCapturer):
    def __init__(self) -> None:
        self._local = threading.local()

    def _get_capturer(self) -> mss.mss:
        capturer = getattr(self._local, "capturer", None)
        if capturer is None:
            capturer = mss.mss()
            self._local.capturer = capturer
        return capturer

    def capture(self, hwnd: int) -> np.ndarray:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        monitor = {"left": left, "top": top, "width": right - left, "height": bottom - top}
        raw = self._get_capturer().grab(monitor)
        return np.array(raw)[:, :, :3]

    def close_current_thread(self) -> None:
        capturer = getattr(self._local, "capturer", None)
        if capturer is not None:
            capturer.close()
            self._local.capturer = None

    def close(self) -> None:
        self.close_current_thread()
