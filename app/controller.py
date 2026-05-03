import logging
import threading

from config import (
    PROCESS_MODULE_NAME,
    WINDOW_TITLE,
    configs,
    infinite_lottery_watcher,
    run_worker,
)
from gbf.memory import ProcessMemory, pid_from_hwnd
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
        self._lottery_lock = threading.Lock()
        self._lottery_thread: threading.Thread | None = None
        self._lottery_stop: threading.Event | None = None
        self._lottery_memory: ProcessMemory | None = None

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
        self.stop_lottery(timeout=3.0)
        result = self.stop(timeout=5.0)
        self._sender.release_all()
        return result

    def is_lottery_running(self) -> bool:
        with self._lottery_lock:
            return self._lottery_thread is not None and self._lottery_thread.is_alive()

    def start_lottery(self) -> tuple[bool, str]:
        with self._lottery_lock:
            if self._lottery_thread is not None and self._lottery_thread.is_alive():
                return False, "Infinite lottery is already running."

            hwnd = self._finder.find(WINDOW_TITLE)
            if not hwnd:
                return False, f"Window not found: {WINDOW_TITLE}"

            pid = pid_from_hwnd(hwnd)
            try:
                memory = ProcessMemory(pid, PROCESS_MODULE_NAME)
            except Exception as exc:
                log.exception("Failed to open process memory")
                return False, (
                    f"Failed to open process memory: {exc}. "
                    "Make sure the game is running in offline mode (EAC disabled)."
                )

            stop_event = threading.Event()
            worker = threading.Thread(
                target=run_worker,
                args=(infinite_lottery_watcher, (memory, stop_event, 1.0)),
                name="lottery-watcher",
                daemon=True,
            )
            self._lottery_memory = memory
            self._lottery_stop = stop_event
            self._lottery_thread = worker
            worker.start()
            return True, "Started infinite lottery."

    def stop_lottery(self, timeout: float = 3.0) -> tuple[bool, str]:
        with self._lottery_lock:
            worker = self._lottery_thread
            stop_event = self._lottery_stop
            memory = self._lottery_memory

        if worker is None or stop_event is None:
            return True, "Infinite lottery is not running."

        stop_event.set()
        worker.join(timeout=timeout)

        if worker.is_alive():
            return False, "Timed out while stopping lottery watcher."

        if memory is not None:
            memory.close()

        with self._lottery_lock:
            if self._lottery_thread is worker:
                self._lottery_thread = None
                self._lottery_stop = None
                self._lottery_memory = None

        return True, "Stopped infinite lottery."

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
