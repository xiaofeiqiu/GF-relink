import logging
import queue
import time
from collections import deque


class UiLogHandler(logging.Handler):
    def __init__(self, sink: queue.SimpleQueue[tuple[float, str]]) -> None:
        super().__init__()
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._sink.put((record.created, self.format(record)))
        except Exception:
            self.handleError(record)


class TimeWindowLogBuffer:
    def __init__(self, window_seconds: float = 60.0) -> None:
        self._window_seconds = window_seconds
        self._queue: queue.SimpleQueue[tuple[float, str]] = queue.SimpleQueue()
        self._records: deque[tuple[float, str]] = deque()

    @property
    def queue(self) -> queue.SimpleQueue[tuple[float, str]]:
        return self._queue

    def drain(self) -> bool:
        now = time.time()
        changed = False

        while True:
            try:
                record = self._queue.get_nowait()
            except queue.Empty:
                break
            self._records.append(record)
            changed = True

        while self._records and now - self._records[0][0] > self._window_seconds:
            self._records.popleft()
            changed = True

        return changed

    def render_text(self) -> str:
        return "\n".join(message for _, message in self._records)
