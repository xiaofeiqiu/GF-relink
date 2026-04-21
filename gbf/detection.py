import cv2
import time
import logging
import numpy as np
import threading
from abc import ABC, abstractmethod
from pathlib import Path

TemplateSource = str | Path | np.ndarray

log = logging.getLogger("detection")


class PatternDetector(ABC):
    @abstractmethod
    def detect(self, target: TemplateSource, screenshot: np.ndarray, threshold: float = 0.8) -> bool:
        pass


class OpenCVTemplateDetector(PatternDetector):
    def __init__(self) -> None:
        self._template_cache: dict[str, np.ndarray] = {}
        self._lock = threading.Lock()

    def _load_template(self, target: str | Path) -> np.ndarray:
        cache_key = str(target)
        with self._lock:
            template = self._template_cache.get(cache_key)
            if template is None:
                template = cv2.imread(cache_key, cv2.IMREAD_GRAYSCALE)
                if template is None:
                    raise FileNotFoundError(f"Template not found: {target}")
                self._template_cache[cache_key] = template
            return template

    def detect(self, target: TemplateSource, screenshot: np.ndarray, threshold: float = 0.8) -> bool:
        t0 = time.perf_counter()
        label = str(target) if isinstance(target, (str, Path)) else "<ndarray>"

        if isinstance(target, (str, Path)):
            template = self._load_template(target)
        elif target.ndim == 3:
            template = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
        else:
            template = target

        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY) if screenshot.ndim == 3 else screenshot

        sh, sw = gray.shape[:2]
        th, tw = template.shape[:2]
        if th > sh or tw > sw:
            raise ValueError(f"Template ({tw}x{th}) larger than screenshot ({sw}x{sh})")

        result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        elapsed = time.perf_counter() - t0
        log.info(f"{label} took {elapsed*1000:.1f}ms (score={max_val:.3f})")
        return bool(max_val >= threshold)
