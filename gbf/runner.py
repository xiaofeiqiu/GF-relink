import threading
from typing import Callable
from .sender import InputSender


MacroFn = Callable[[InputSender, int, threading.Event], None]


class Runner:
    def __init__(self, sender: InputSender):
        self.sender = sender

    def run(self, hwnd: int, macro_fn: MacroFn, stop_event: threading.Event) -> None:
        macro_fn(self.sender, hwnd, stop_event)
