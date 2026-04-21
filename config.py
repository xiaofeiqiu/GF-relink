import time
import random
import threading
import logging
import win32gui
from gbf.runner import MacroFn
from gbf.sender import InputSender
from gbf.capture import MssScreenCapturer, ScreenCapturer
from gbf.detection import OpenCVTemplateDetector, PatternDetector

log = logging.getLogger("config")

WINDOW_TITLE = "Granblue Fantasy: Relink"

SHILAIMU = "shilaimu"


def wait_or_stop(stop_event: threading.Event, timeout: float) -> bool:
    return stop_event.wait(timeout)


class CombinedEvent:
    def __init__(self, *events: threading.Event):
        self._events = events

    def is_set(self) -> bool:
        return all(event.is_set() for event in self._events)


def is_window_focused(hwnd: int) -> bool:
    return win32gui.GetForegroundWindow() == hwnd


def wait_until_focused(
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
    interval: float = 0.1,
) -> bool:
    while not stop_event.is_set():
        if is_window_focused(hwnd):
            focus_event.set()
            return True
        focus_event.clear()
        if wait_or_stop(stop_event, interval):
            break
    return False


def run_worker(
    target,
    args: tuple,
    capturer: ScreenCapturer | None = None,
) -> None:
    try:
        target(*args)
    except Exception:
        log.exception("Worker thread crashed")
    finally:
        if capturer is not None:
            capturer.close_current_thread()


def keep_attack_enabled_while_attack_button_is_visible(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    hwnd: int,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
    interval: float = 1.0,
    threshold: float = 0.8,
) -> None:
    while not stop_event.is_set():
        if not wait_until_focused(hwnd, focus_event, stop_event):
            break
        if detector.detect("templates/attack.png", capturer.capture(hwnd), threshold):
            can_attack.set()
        else:
            can_attack.clear()
        if wait_or_stop(stop_event, interval):
            break


def spam_left_clicks_while_attack_is_enabled(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
    interval: float = 0.05,
) -> None:
    while not stop_event.is_set():
        if not focus_event.wait(0.1):
            continue
        if not can_attack.wait(0.1):
            continue
        if stop_event.is_set() or not focus_event.is_set():
            break
        sender.click_left()
        if wait_or_stop(stop_event, interval):
            break


def move(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
) -> None:
    movement_allowed = CombinedEvent(focus_event, can_attack)
    while not stop_event.is_set():
        if not focus_event.wait(0.1):
            continue
        if not can_attack.wait(0.1):
            continue
        if not movement_allowed.is_set():
            continue
        log.info("Hold w for 10.0s")
        sender.hold("w", 10.0, hold_while=movement_allowed)
        if stop_event.is_set() or not movement_allowed.is_set():
            continue
        side_key = random.choice(["a", "d"])
        log.info(f"Hold {side_key} for 3.0s")
        sender.hold(side_key, 3.0, hold_while=movement_allowed)


def press_enter_when_confirm_dialog_is_visible(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
    interval: float = 1.0,
    threshold: float = 0.8,
) -> None:
    while not stop_event.is_set():
        if not wait_until_focused(hwnd, focus_event, stop_event):
            break
        if detector.detect("templates/confirm.png", capturer.capture(hwnd), threshold):
            log.info("templates/confirm.png found")
            if wait_or_stop(stop_event, 0.1):
                break
            sender.press("enter")
            log.info("Press enter")
        if wait_or_stop(stop_event, interval):
            break


def repeat_again(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
    interval: float = 1.0,
    threshold: float = 0.8,
) -> None:
    while not stop_event.is_set():
        if not wait_until_focused(hwnd, focus_event, stop_event):
            break
        if detector.detect("templates/cancle-repeat.png", capturer.capture(hwnd), threshold):
            log.info("templates/cancle-repeat.png found")
            if wait_or_stop(stop_event, 2.0):
                break
            sender.press("enter")
            log.info("Press enter")
        if wait_or_stop(stop_event, interval):
            break


def first_time_repeat(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
    interval: float = 1.0,
    threshold: float = 0.8,
) -> None:
    while not stop_event.is_set():
        if not wait_until_focused(hwnd, focus_event, stop_event):
            break
        screenshot = capturer.capture(hwnd)
        if detector.detect("templates/again.png", screenshot, threshold) and not detector.detect(
            "templates/cancle-repeat.png", screenshot, threshold
        ):
            log.info("templates/again.png found without templates/cancle-repeat.png")
            if wait_or_stop(stop_event, 0.1):
                break
            sender.press("3")
            log.info("Press 3")
            if wait_or_stop(stop_event, 0.1):
                break
            sender.press("enter")
            log.info("Press enter")
        if wait_or_stop(stop_event, interval):
            break


def cycle_repeat(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
    interval: float = 1.0,
    threshold: float = 0.8,
) -> None:
    while not stop_event.is_set():
        if not wait_until_focused(hwnd, focus_event, stop_event):
            break
        if detector.detect("templates/cycle-repeat.bmp", capturer.capture(hwnd), threshold):
            log.info("templates/cycle-repeat.bmp found")
            if wait_or_stop(stop_event, 0.1):
                break
            sender.press("w")
            log.info("Press w")
            if wait_or_stop(stop_event, 0.1):
                break
            sender.press("enter")
            log.info("Press enter")
        if wait_or_stop(stop_event, interval):
            break


def aoyi(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
    interval: float = 1.0,
    threshold: float = 0.8,
) -> None:
    while not stop_event.is_set():
        if not wait_until_focused(hwnd, focus_event, stop_event):
            break
        if detector.detect("templates/aoyi.bmp", capturer.capture(hwnd), threshold):
            log.info("templates/aoyi.bmp found")
            if wait_or_stop(stop_event, 0.1):
                break
            sender.press("g")
            log.info("Press g")
        if wait_or_stop(stop_event, interval):
            break


def press_r_when_r_template_is_visible(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
    interval: float = 1.0,
    threshold: float = 0.95,
) -> None:
    while not stop_event.is_set():
        if not wait_until_focused(hwnd, focus_event, stop_event):
            break
        if detector.detect("templates/r.bmp", capturer.capture(hwnd), threshold):
            log.info("templates/r.bmp found")
            if wait_or_stop(stop_event, 0.1):
                break
            sender.press("r")
            log.info("Press r")
        if wait_or_stop(stop_event, interval):
            break


def fire_skill(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
    key_interval: float = 0.5,
    cycle_interval: float = 5.0,
) -> None:
    combo_keys = ["2", "3", "4"]
    if wait_or_stop(stop_event, cycle_interval):
        return
    while not stop_event.is_set():
        if not focus_event.wait(0.1):
            continue
        if not can_attack.wait(0.1):
            continue
        if stop_event.is_set() or not focus_event.is_set():
            break
        sender.click_middle()
        log.info("Click middle")
        if wait_or_stop(stop_event, 0.1):
            break
        for key in combo_keys:
            if stop_event.is_set() or not can_attack.is_set() or not focus_event.is_set():
                break
            sender.press(key)
            log.info(f"Press {key}")
            if wait_or_stop(stop_event, key_interval):
                break
        if wait_or_stop(stop_event, cycle_interval):
            break


def keep_report_confirmation_enabled_while_report_is_visible(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    hwnd: int,
    focus_event: threading.Event,
    report_visible: threading.Event,
    stop_event: threading.Event,
    interval: float = 1.0,
    threshold: float = 0.8,
) -> None:
    while not stop_event.is_set():
        if not wait_until_focused(hwnd, focus_event, stop_event):
            break
        if detector.detect("templates/report.bmp", capturer.capture(hwnd), threshold):
            report_visible.set()
        else:
            report_visible.clear()
        if wait_or_stop(stop_event, interval):
            break


def spam_enter_while_report_confirmation_is_enabled(
    sender: InputSender,
    focus_event: threading.Event,
    report_visible: threading.Event,
    stop_event: threading.Event,
    interval: float = 0.2,
) -> None:
    while not stop_event.is_set():
        if not focus_event.wait(0.1):
            continue
        if not report_visible.wait(0.1):
            continue
        if stop_event.is_set() or not focus_event.is_set():
            break
        sender.press("enter")
        log.info("Press enter")
        if wait_or_stop(stop_event, interval):
            break


def monitor_window_focus(
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    can_attack: threading.Event,
    report_visible: threading.Event,
    stop_event: threading.Event,
    interval: float = 0.1,
) -> None:
    was_focused = False
    while not stop_event.is_set():
        focused = is_window_focused(hwnd)
        if focused:
            if not was_focused:
                log.info("Target window focused, resuming watchers")
            focus_event.set()
        else:
            if was_focused:
                log.info("Target window not focused, pausing watchers")
                sender.release_all()
            focus_event.clear()
            can_attack.clear()
            report_visible.clear()
        was_focused = focused
        if wait_or_stop(stop_event, interval):
            break


def create_attack_state_watcher_thread(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    hwnd: int,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(
            keep_attack_enabled_while_attack_button_is_visible,
            (capturer, detector, hwnd, focus_event, can_attack, stop_event, 1.0, 0.8),
            capturer,
        ),
    )


def create_basic_attack_spam_thread(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(spam_left_clicks_while_attack_is_enabled, (sender, focus_event, can_attack, stop_event, 0.05)),
    )


def create_combat_movement_thread(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(move, (sender, focus_event, can_attack, stop_event)),
    )


def create_confirm_dialog_handler_thread(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(
            press_enter_when_confirm_dialog_is_visible,
            (capturer, detector, sender, hwnd, focus_event, stop_event, 1.0, 0.8),
            capturer,
        ),
    )


def repeat_again_watcher(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(repeat_again, (capturer, detector, sender, hwnd, focus_event, stop_event, 1.0, 0.8), capturer),
    )


def first_time_repeat_watcher(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(first_time_repeat, (capturer, detector, sender, hwnd, focus_event, stop_event, 1.0, 0.8), capturer),
    )


def cycle_repeat_watcher(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(cycle_repeat, (capturer, detector, sender, hwnd, focus_event, stop_event, 1.0, 0.9), capturer),
    )


def aoyi_watcher(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(aoyi, (capturer, detector, sender, hwnd, focus_event, stop_event, 1.0, 0.8), capturer),
    )


def create_combo_skill_rotation_thread(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(fire_skill, (sender, focus_event, can_attack, stop_event, 1.0, 5.0)),
    )


def create_r_template_watcher_thread(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(
            press_r_when_r_template_is_visible,
            (capturer, detector, sender, hwnd, focus_event, stop_event, 1.0, 0.95),
            capturer,
        ),
    )


def create_report_state_watcher_thread(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    hwnd: int,
    focus_event: threading.Event,
    report_visible: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(
            keep_report_confirmation_enabled_while_report_is_visible,
            (capturer, detector, hwnd, focus_event, report_visible, stop_event, 1.0, 0.8),
            capturer,
        ),
    )


def create_report_confirm_spam_thread(
    sender: InputSender,
    focus_event: threading.Event,
    report_visible: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(spam_enter_while_report_confirmation_is_enabled, (sender, focus_event, report_visible, stop_event, 0.2)),
    )


def shilaimu(sender: InputSender, hwnd: int) -> None:
    capturer = MssScreenCapturer()
    detector = OpenCVTemplateDetector()

    focus_event = threading.Event()
    can_attack = threading.Event()
    report_visible = threading.Event()
    stop_event = threading.Event()

    threads = [
        threading.Thread(
            target=run_worker,
            args=(monitor_window_focus, (sender, hwnd, focus_event, can_attack, report_visible, stop_event)),
        ),
        create_attack_state_watcher_thread(capturer, detector, hwnd, focus_event, can_attack, stop_event),
        create_basic_attack_spam_thread(sender, focus_event, can_attack, stop_event),
        create_combo_skill_rotation_thread(sender, focus_event, can_attack, stop_event),
        create_combat_movement_thread(sender, focus_event, can_attack, stop_event),
        create_confirm_dialog_handler_thread(capturer, detector, sender, hwnd, focus_event, stop_event),
        first_time_repeat_watcher(capturer, detector, sender, hwnd, focus_event, stop_event),
        repeat_again_watcher(capturer, detector, sender, hwnd, focus_event, stop_event),
        cycle_repeat_watcher(capturer, detector, sender, hwnd, focus_event, stop_event),
        aoyi_watcher(capturer, detector, sender, hwnd, focus_event, stop_event),
        create_r_template_watcher_thread(capturer, detector, sender, hwnd, focus_event, stop_event),
        create_report_state_watcher_thread(capturer, detector, hwnd, focus_event, report_visible, stop_event),
        create_report_confirm_spam_thread(sender, focus_event, report_visible, stop_event),
    ]

    try:
        for t in threads:
            t.start()

        threads[1].join()
    finally:
        stop_event.set()
        focus_event.set()
        can_attack.set()
        report_visible.set()
        for t in threads:
            t.join(timeout=1.0)


configs: dict[str, MacroFn] = {
    SHILAIMU: shilaimu,
}
