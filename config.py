import time
import random
import struct
import threading
import logging
import win32gui
from app.paths import template_path
from gbf.runner import MacroFn
from gbf.sender import InputSender
from gbf.capture import MssScreenCapturer, ScreenCapturer
from gbf.detection import OpenCVTemplateDetector, PatternDetector
from gbf.memory import ProcessMemory

log = logging.getLogger("config")

WINDOW_TITLE = "Granblue Fantasy: Relink"
PROCESS_MODULE_NAME = "granblue_fantasy_relink.exe"
LOTTERY_TICKET_BASE_OFFSET = 0x05E48188
LOTTERY_TICKET_POINTER_OFFSETS = (0x2E8, 0x78, 0x504)
LOTTERY_TICKET_TARGET = 999
ITEM_SCAN_BACK = 0x9000
ITEM_SCAN_FORWARD = 0xA000
ITEM_SLOT_TYPES = frozenset({4, 12})
ITEM_ID_MIN = 1000
ITEM_ID_MAX = 100000
ITEM_QTY_MIN = 1
ITEM_QTY_MAX = 999

SHILAIMU = "shilaimu"

ATTACK_TEMPLATE = template_path("attack.png")
CONFIRM_TEMPLATE = template_path("confirm.png")
CANCEL_REPEAT_TEMPLATE = template_path("cancle-repeat.png")
AGAIN_TEMPLATE = template_path("again.png")
CYCLE_REPEAT_TEMPLATE = template_path("cycle-repeat.bmp")
AOYI_TEMPLATE = template_path("aoyi.bmp")
R_TEMPLATE = template_path("r.bmp")
REPORT_TEMPLATE = template_path("report.bmp")
FUHUO_TEMPLATE = template_path("fuhuo.bmp")


def wait_or_stop(stop_event: threading.Event, timeout: float) -> bool:
    return stop_event.wait(timeout)


def wait_until_event_set(
    event: threading.Event,
    stop_event: threading.Event,
    interval: float = 0.1,
) -> bool:
    while not stop_event.is_set():
        if event.wait(interval):
            return True
    return False


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
        if detector.detect(ATTACK_TEMPLATE, capturer.capture(hwnd), threshold):
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
        if not wait_until_event_set(focus_event, stop_event):
            continue
        if not wait_until_event_set(can_attack, stop_event):
            continue
        if stop_event.is_set() or not focus_event.is_set() or not can_attack.is_set():
            continue
        sender.click_left()
        if wait_or_stop(stop_event, interval):
            break


def spam_c_while_attack_is_enabled(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
    hold_duration: float = 1.5,
    interval: float = 5.0,
) -> None:
    hold_allowed = CombinedEvent(focus_event, can_attack)
    while not stop_event.is_set():
        if not wait_until_event_set(focus_event, stop_event):
            continue
        if not wait_until_event_set(can_attack, stop_event):
            continue
        if stop_event.is_set() or not hold_allowed.is_set():
            continue
        log.info("Hold c for %.1fs", hold_duration)
        sender.hold("c", hold_duration, hold_while=hold_allowed, stop_event=stop_event)
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
        if not wait_until_event_set(focus_event, stop_event):
            continue
        if not wait_until_event_set(can_attack, stop_event):
            continue
        if not movement_allowed.is_set():
            continue
        log.info("Hold w for 10.0s")
        sender.hold("w", 10.0, hold_while=movement_allowed, stop_event=stop_event)
        if stop_event.is_set() or not movement_allowed.is_set():
            continue
        side_key = random.choice(["a", "d"])
        log.info(f"Hold {side_key} for 3.0s")
        sender.hold(side_key, 3.0, hold_while=movement_allowed, stop_event=stop_event)


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
        if detector.detect(CONFIRM_TEMPLATE, capturer.capture(hwnd), threshold):
            log.info("%s found", CONFIRM_TEMPLATE)
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
        if detector.detect(CANCEL_REPEAT_TEMPLATE, capturer.capture(hwnd), threshold):
            log.info("%s found", CANCEL_REPEAT_TEMPLATE)
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
        if detector.detect(AGAIN_TEMPLATE, screenshot, threshold) and not detector.detect(
            CANCEL_REPEAT_TEMPLATE, screenshot, threshold
        ):
            log.info("%s found without %s", AGAIN_TEMPLATE, CANCEL_REPEAT_TEMPLATE)
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
        if detector.detect(CYCLE_REPEAT_TEMPLATE, capturer.capture(hwnd), threshold):
            log.info("%s found", CYCLE_REPEAT_TEMPLATE)
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
        if detector.detect(AOYI_TEMPLATE, capturer.capture(hwnd), threshold):
            log.info("%s found", AOYI_TEMPLATE)
            if wait_or_stop(stop_event, 0.1):
                break
            sender.press("g")
            log.info("Press g")
        if wait_or_stop(stop_event, interval):
            break


def keep_fuhuo_enabled_while_fuhuo_template_is_visible(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    hwnd: int,
    focus_event: threading.Event,
    fuhuo_visible: threading.Event,
    stop_event: threading.Event,
    interval: float = 0.2,
    threshold: float = 0.7
) -> None:
    while not stop_event.is_set():
        if not wait_until_focused(hwnd, focus_event, stop_event):
            break
        if detector.detect(FUHUO_TEMPLATE, capturer.capture(hwnd), threshold):
            fuhuo_visible.set()
        else:
            fuhuo_visible.clear()
        if wait_or_stop(stop_event, interval):
            break


def hold_v_while_fuhuo_is_enabled(
    sender: InputSender,
    focus_event: threading.Event,
    fuhuo_visible: threading.Event,
    stop_event: threading.Event,
    max_hold_seconds: float = 30.0,
) -> None:
    hold_allowed = CombinedEvent(focus_event, fuhuo_visible)
    while not stop_event.is_set():
        if not wait_until_event_set(focus_event, stop_event):
            continue
        if not wait_until_event_set(fuhuo_visible, stop_event):
            continue
        if stop_event.is_set() or not hold_allowed.is_set():
            continue
        log.info("Hold v while %s visible", FUHUO_TEMPLATE)
        sender.hold("v", max_hold_seconds, hold_while=hold_allowed, stop_event=stop_event)


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
        if detector.detect(R_TEMPLATE, capturer.capture(hwnd), threshold):
            log.info("%s found", R_TEMPLATE)
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
    key_hold_duration: float = 0.1,
    key_interval: float = 0.5,
    cycle_interval: float = 5.0,
) -> None:
    combo_keys = ["2", "3", "4"]
    hold_allowed = CombinedEvent(focus_event, can_attack)
    if wait_or_stop(stop_event, cycle_interval):
        return
    while not stop_event.is_set():
        if not wait_until_event_set(focus_event, stop_event):
            continue
        if not wait_until_event_set(can_attack, stop_event):
            continue
        if stop_event.is_set() or not hold_allowed.is_set():
            continue
        sender.click_middle()
        log.info("Click middle")
        if wait_or_stop(stop_event, 0.1):
            break
        for key in combo_keys:
            if stop_event.is_set() or not hold_allowed.is_set():
                break
            log.info("Hold %s for %.1fs", key, key_hold_duration)
            sender.hold(key, key_hold_duration, hold_while=hold_allowed, stop_event=stop_event)
            if wait_or_stop(stop_event, key_interval):
                break
        if wait_or_stop(stop_event, cycle_interval):
            break


def fire_skill_1(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
    hold_duration: float = 5.0,
    cycle_interval: float = 15.0,
) -> None:
    hold_allowed = CombinedEvent(focus_event, can_attack)
    if wait_or_stop(stop_event, cycle_interval):
        return
    while not stop_event.is_set():
        if not wait_until_event_set(focus_event, stop_event):
            continue
        if not wait_until_event_set(can_attack, stop_event):
            continue
        if stop_event.is_set() or not hold_allowed.is_set():
            continue
        log.info("Hold 1 for %.1fs", hold_duration)
        sender.hold("1", hold_duration, hold_while=hold_allowed, stop_event=stop_event)
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
        if detector.detect(REPORT_TEMPLATE, capturer.capture(hwnd), threshold):
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
        if not wait_until_event_set(focus_event, stop_event):
            continue
        if not wait_until_event_set(report_visible, stop_event):
            continue
        if stop_event.is_set() or not focus_event.is_set() or not report_visible.is_set():
            continue
        sender.press("enter")
        log.info("Press enter")
        if wait_or_stop(stop_event, interval):
            break


def _refill_item_slots(memory: ProcessMemory, known_slot: int) -> tuple[int, int]:
    start_addr = known_slot - ITEM_SCAN_BACK
    end_addr = known_slot + ITEM_SCAN_FORWARD
    length = (end_addr + 12) - start_addr
    blob = memory.read_bytes(start_addr, length)
    n_ints = length // 4
    ints = struct.unpack(f"<{n_ints}I", blob[: n_ints * 4])

    found = 0
    changed = 0
    for i in range(n_ints - 2):
        qty = ints[i]
        typ = ints[i + 1]
        item_id = ints[i + 2]
        if (
            ITEM_QTY_MIN <= qty <= ITEM_QTY_MAX
            and typ in ITEM_SLOT_TYPES
            and ITEM_ID_MIN <= item_id <= ITEM_ID_MAX
        ):
            found += 1
            if qty < LOTTERY_TICKET_TARGET:
                memory.write_uint32(start_addr + i * 4, LOTTERY_TICKET_TARGET)
                changed += 1
    return found, changed


def infinite_lottery_watcher(
    memory: ProcessMemory,
    stop_event: threading.Event,
    interval: float = 1.0,
) -> None:
    while not stop_event.is_set():
        if wait_or_stop(stop_event, interval):
            break
        try:
            known_slot = memory.resolve_pointer_chain(
                LOTTERY_TICKET_BASE_OFFSET, LOTTERY_TICKET_POINTER_OFFSETS
            )
            found, changed = _refill_item_slots(memory, known_slot)
            if changed > 0:
                log.info("Item refill: slots found=%d, refilled=%d", found, changed)
        except Exception:
            log.exception("Lottery watcher iteration failed")


def monitor_window_focus(
    sender: InputSender,
    hwnd: int,
    focus_event: threading.Event,
    can_attack: threading.Event,
    report_visible: threading.Event,
    fuhuo_visible: threading.Event,
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
            fuhuo_visible.clear()
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


def create_c_key_spam_thread(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(spam_c_while_attack_is_enabled, (sender, focus_event, can_attack, stop_event, 1.5, 5.0)),
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


def create_fuhuo_state_watcher_thread(
    capturer: ScreenCapturer,
    detector: PatternDetector,
    hwnd: int,
    focus_event: threading.Event,
    fuhuo_visible: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(
            keep_fuhuo_enabled_while_fuhuo_template_is_visible,
            (capturer, detector, hwnd, focus_event, fuhuo_visible, stop_event, 0.2, 0.8),
            capturer,
        ),
    )


def create_fuhuo_v_hold_thread(
    sender: InputSender,
    focus_event: threading.Event,
    fuhuo_visible: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(hold_v_while_fuhuo_is_enabled, (sender, focus_event, fuhuo_visible, stop_event, 30.0)),
    )


def create_combo_skill_rotation_thread(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(fire_skill, (sender, focus_event, can_attack, stop_event, 0.1, 1.0, 5.0)),
    )


def create_skill_1_hold_thread(
    sender: InputSender,
    focus_event: threading.Event,
    can_attack: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread:
    return threading.Thread(
        target=run_worker,
        args=(fire_skill_1, (sender, focus_event, can_attack, stop_event, 5.0, 15.0)),
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


def shilaimu(sender: InputSender, hwnd: int, stop_event: threading.Event) -> None:
    capturer = MssScreenCapturer()
    detector = OpenCVTemplateDetector()

    focus_event = threading.Event()
    can_attack = threading.Event()
    report_visible = threading.Event()
    fuhuo_visible = threading.Event()

    threads = [
        threading.Thread(
            target=run_worker,
            args=(
                monitor_window_focus,
                (sender, hwnd, focus_event, can_attack, report_visible, fuhuo_visible, stop_event),
            ),
        ),
        create_attack_state_watcher_thread(capturer, detector, hwnd, focus_event, can_attack, stop_event),
        create_basic_attack_spam_thread(sender, focus_event, can_attack, stop_event),
        create_c_key_spam_thread(sender, focus_event, can_attack, stop_event),
        create_combo_skill_rotation_thread(sender, focus_event, can_attack, stop_event),
        create_skill_1_hold_thread(sender, focus_event, can_attack, stop_event),
        create_combat_movement_thread(sender, focus_event, can_attack, stop_event),
        create_confirm_dialog_handler_thread(capturer, detector, sender, hwnd, focus_event, stop_event),
        first_time_repeat_watcher(capturer, detector, sender, hwnd, focus_event, stop_event),
        repeat_again_watcher(capturer, detector, sender, hwnd, focus_event, stop_event),
        cycle_repeat_watcher(capturer, detector, sender, hwnd, focus_event, stop_event),
        aoyi_watcher(capturer, detector, sender, hwnd, focus_event, stop_event),
        create_fuhuo_state_watcher_thread(capturer, detector, hwnd, focus_event, fuhuo_visible, stop_event),
        create_fuhuo_v_hold_thread(sender, focus_event, fuhuo_visible, stop_event),
        create_r_template_watcher_thread(capturer, detector, sender, hwnd, focus_event, stop_event),
        create_report_state_watcher_thread(capturer, detector, hwnd, focus_event, report_visible, stop_event),
        create_report_confirm_spam_thread(sender, focus_event, report_visible, stop_event),
    ]

    try:
        for t in threads:
            t.start()

        threads[0].join()
    finally:
        stop_event.set()
        sender.release_all()
        for t in threads:
            t.join(timeout=2.0)


configs: dict[str, MacroFn] = {
    SHILAIMU: shilaimu,
}
