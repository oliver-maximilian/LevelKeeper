"""PID-based lockfile preventing overlapping runs."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class LockHeldError(RuntimeError):
    pass


class LockFile:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._held = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                if attempt == 0 and self._clear_if_stale():
                    continue
                raise LockHeldError(
                    f"lock file {self.path} already held by a running process"
                ) from None
            else:
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self._held = True
                return
        raise LockHeldError(f"lock file {self.path} already held by a running process")

    def _clear_if_stale(self) -> bool:
        try:
            pid = int(self.path.read_text().strip())
        except (OSError, ValueError):
            logger.warning("lock file %s unreadable/corrupt, removing", self.path)
            self.path.unlink(missing_ok=True)
            return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            logger.warning(
                "lock file %s references dead pid %s, removing stale lock", self.path, pid
            )
            self.path.unlink(missing_ok=True)
            return True
        except PermissionError:
            return False
        return False

    def release(self) -> None:
        if self._held:
            self.path.unlink(missing_ok=True)
            self._held = False

    def __enter__(self) -> LockFile:
        self.acquire()
        return self

    def __exit__(self, *exc_info) -> None:
        self.release()
