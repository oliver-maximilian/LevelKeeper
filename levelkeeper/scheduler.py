"""Internal interval scheduler (alternative to driving the container via host cron)."""

from __future__ import annotations

import logging
import re
import time
from typing import Callable

logger = logging.getLogger(__name__)

_INTERVAL_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhd]?)\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "": 1}


def parse_interval(value: str) -> float | None:
    """Parse "1h", "30m", "3600" into seconds. Empty/blank => None (run once)."""
    if not value or not value.strip():
        return None
    match = _INTERVAL_RE.match(value)
    if not match:
        raise ValueError(f"invalid run_interval {value!r}")
    number, unit = match.groups()
    return float(number) * _UNIT_SECONDS[unit.lower()]


def run_forever(run_once: Callable[[], None], interval_seconds: float, should_stop: Callable[[], bool]) -> None:
    step = 1.0
    while not should_stop():
        try:
            run_once()
        except Exception:
            logger.exception("unhandled error during scheduled run; will retry next interval")
        slept = 0.0
        while slept < interval_seconds and not should_stop():
            time.sleep(min(step, interval_seconds - slept))
            slept += step
