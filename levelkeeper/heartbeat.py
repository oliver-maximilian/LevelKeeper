"""Heartbeat ping (Uptime Kuma)."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def send_heartbeat(url: str, timeout: float = 10.0) -> bool:
    """GET the push URL. Never raises."""
    if not url:
        return False
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - scheme validated in config
            resp.read()
        logger.info("heartbeat sent")
        return True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("heartbeat failed: %s", exc)
        return False
