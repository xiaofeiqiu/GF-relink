import logging
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from config import SHILAIMU, configs

from .controller import MacroController
from .log_buffer import TimeWindowLogBuffer, UiLogHandler


class MacroApp:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._root.title("GBF Macro")
        self._root.geometry("720x420")
        self._root.minsize(600, 360)

        self._controller = MacroController()
        self._log_buffer = TimeWindowLogBuffer(window_seconds=60.0)
        self._log_handler: UiLogHandler | None = None
        self._closing = False
        self._stop_requested = False

        self._build_ui()
        self._install_logging()
        self._refresh_controls()
        self._poll_logs()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self._root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Config").pack(side=tk.LEFT)

        config_names = list(configs.keys())
        default_name = SHILAIMU if SHILAIMU in configs else (config_names[0] if config_names else "")
        self._config_name = tk.StringVar(value=default_name)
        self._config_dropdown = ttk.Combobox(
            controls,
            textvariable=self._config_name,
            values=config_names,
            state="readonly",
            width=24,
        )
        self._config_dropdown.pack(side=tk.LEFT, padx=(8, 12))

        self._start_button = ttk.Button(controls, text="Start", command=self._on_start)
        self._start_button.pack(side=tk.LEFT)

        self._stop_button = ttk.Button(controls, text="Stop", command=self._on_stop)
        self._stop_button.pack(side=tk.LEFT, padx=(8, 0))

        self._lottery_button = ttk.Button(controls, text="无限抽奖: OFF", command=self._on_toggle_lottery)
        self._lottery_button.pack(side=tk.LEFT, padx=(16, 0))

        self._status_var = tk.StringVar(value="Idle")
        ttk.Label(frame, textvariable=self._status_var).pack(anchor=tk.W, pady=(10, 8))

        self._log_text = scrolledtext.ScrolledText(frame, state=tk.DISABLED, wrap=tk.WORD, height=16)
        self._log_text.pack(fill=tk.BOTH, expand=True)

    def _install_logging(self) -> None:
        handler = UiLogHandler(self._log_buffer.queue)
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
        )
        logging.getLogger().addHandler(handler)
        self._log_handler = handler

    def _remove_logging(self) -> None:
        if self._log_handler is None:
            return
        logging.getLogger().removeHandler(self._log_handler)
        self._log_handler.close()
        self._log_handler = None

    def _on_start(self) -> None:
        started, message = self._controller.start(self._config_name.get())
        if not started:
            messagebox.showerror("Unable to start", message)
            return
        self._status_var.set(message)
        self._refresh_controls()

    def _on_toggle_lottery(self) -> None:
        if self._controller.is_lottery_running():
            ok, message = self._controller.stop_lottery()
        else:
            ok, message = self._controller.start_lottery()
        if not ok:
            messagebox.showerror("无限抽奖", message)
        self._refresh_controls()

    def _on_stop(self) -> None:
        if self._stop_requested:
            return
        self._stop_requested = True
        self._status_var.set("Stopping...")
        self._refresh_controls()
        threading.Thread(target=self._stop_in_background, name="ui-stop", daemon=True).start()

    def _stop_in_background(self) -> None:
        stopped, message = self._controller.stop()
        try:
            self._root.after(0, lambda: self._finish_stop(stopped, message))
        except tk.TclError:
            pass

    def _finish_stop(self, stopped: bool, message: str) -> None:
        self._stop_requested = False
        if not stopped and not self._closing:
            messagebox.showerror("Unable to stop", message)
        self._status_var.set(message)
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        running = self._controller.is_running()
        self._start_button.config(state=tk.DISABLED if running else tk.NORMAL)
        self._config_dropdown.config(state="disabled" if running else "readonly")
        self._stop_button.config(state=tk.NORMAL if running and not self._stop_requested else tk.DISABLED)
        lottery_on = self._controller.is_lottery_running()
        self._lottery_button.config(text=f"无限抽奖: {'ON' if lottery_on else 'OFF'}")
        if running and not self._status_var.get().startswith("Stopping"):
            self._status_var.set(f"Running {self._config_name.get()}")
        elif not running and self._status_var.get().startswith("Running"):
            self._status_var.set("Idle")

    def _poll_logs(self) -> None:
        if self._log_buffer.drain():
            self._render_logs()

        self._refresh_controls()
        if not self._closing:
            self._root.after(250, self._poll_logs)

    def _render_logs(self) -> None:
        self._log_text.config(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.insert(tk.END, self._log_buffer.render_text())
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    def _on_close(self) -> None:
        self._closing = True
        self._status_var.set("Closing...")
        self._refresh_controls()
        self._remove_logging()
        self._controller.close()
        self._root.destroy()
