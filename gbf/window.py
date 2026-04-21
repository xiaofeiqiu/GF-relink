import win32gui
import win32con
import time
from abc import ABC, abstractmethod


class WindowFinder(ABC):
    @abstractmethod
    def find(self, title: str) -> int | None:
        pass


class Win32WindowFinder(WindowFinder):
    def find(self, title: str) -> int | None:
        result = []
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                if title.lower() in win32gui.GetWindowText(hwnd).lower():
                    result.append(hwnd)
        win32gui.EnumWindows(callback, None)
        return result[0] if result else None


class WindowFocuser(ABC):
    @abstractmethod
    def focus(self, hwnd: int) -> None:
        pass


class Win32WindowFocuser(WindowFocuser):
    def focus(self, hwnd: int) -> None:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
