import time
import logging
from gbf.window import Win32WindowFinder
from gbf.sender import DirectInputSender
from gbf.runner import Runner
from config import WINDOW_TITLE, configs, SHILAIMU

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def main():
    finder = Win32WindowFinder()
    sender = DirectInputSender()
    runner = Runner(sender)

    hwnd = finder.find(WINDOW_TITLE)
    if not hwnd:
        log.error(f"Window not found: {WINDOW_TITLE}")
        input("Press Enter to exit...")
        return

    config = configs[SHILAIMU]

    log.info("Window found, starting in 3s...")
    time.sleep(3)

    try:
        runner.run(hwnd, config)
    except KeyboardInterrupt:
        log.info("Interrupted, cleaning up...")
    finally:
        sender.release_all()
    log.info("Done!")


if __name__ == "__main__":
    main()

