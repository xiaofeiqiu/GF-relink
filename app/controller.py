import logging
import threading

from config import WINDOW_TITLE, configs
from gbf.runner import Runner
from gbf.sender import DirectInputSender
from gbf.window import Win32WindowFinder

log = logging.getLogger("app.controller")


class MacroController:
    def __init__(self) -> None:
        self._finder = Win32WindowFinder()
        self._sender = DirectInputSender()
        self._runner = Runner(self._sender)
        self._lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None

    def is_running(self) -> bool:
        with self._lock:
            return self._worker_thread is not None and self._worker_thread.is_alive()

    def start(self, config_name: str) -> tuple[bool, str]:
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return False, "A macro is already running."

            hwnd = self._finder.find(WINDOW_TITLE)
            if not hwnd:
                return False, f"Window not found: {WINDOW_TITLE}"

            macro_fn = configs.get(config_name)
            if macro_fn is None:
                return False, f"Unknown config: {config_name}"

            stop_event = threading.Event()
            worker_thread = threading.Thread(
                target=self._run_macro,
                args=(hwnd, config_name, macro_fn, stop_event),
                name=f"macro-{config_name}",
            )
            self._stop_event = stop_event
            self._worker_thread = worker_thread
            worker_thread.start()
            return True, f"Started {config_name}."

    def stop(self, timeout: float = 5.0) -> tuple[bool, str]:
        with self._lock:
            worker_thread = self._worker_thread
            stop_event = self._stop_event

        if worker_thread is None or stop_event is None:
            return True, "Nothing is running."

        stop_event.set()
        self._sender.release_all()
        worker_thread.join(timeout=timeout)

        if worker_thread.is_alive():
            return False, "Timed out while waiting for the macro thread to stop."
        return True, "Stopped."

    def close(self) -> tuple[bool, str]:
        result = self.stop(timeout=5.0)
        self._sender.release_all()
        return result

    def _run_macro(self, hwnd: int, config_name: str, macro_fn, stop_event: threading.Event) -> None:
        log.info("Starting config '%s'", config_name)
        try:
            self._runner.run(hwnd, macro_fn, stop_event)
        except Exception:
            log.exception("Macro '%s' crashed", config_name)
        finally:
            self._sender.release_all()
            with self._lock:
                if self._stop_event is stop_event:
                    self._stop_event = None
                if self._worker_thread is threading.current_thread():
                    self._worker_thread = None
            log.info("Config '%s' stopped", config_name)
