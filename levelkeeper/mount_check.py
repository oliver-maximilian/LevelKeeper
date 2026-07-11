"""NAS mount verification.

A Docker bind mount always shows up as a mount point inside the container,
even when the *host* side failed to mount the NAS share (Docker will happily
bind-mount whatever empty local directory happens to sit at that host path).
So `os.path.ismount()` alone is not reliable from inside the container. The
authoritative check is a marker file that only exists on the real NAS share -
create it once during setup, see README.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class MountCheckResult:
    ok: bool
    reason: str


def check_mount(archive_root: str | Path, marker_filename: str) -> MountCheckResult:
    root = Path(archive_root)
    if not root.is_dir():
        return MountCheckResult(False, f"archive root {root} does not exist or is not a directory")
    marker = root / marker_filename
    if not marker.is_file():
        return MountCheckResult(
            False,
            f"mount marker file {marker} not found - NAS share is likely not "
            "mounted on the host (or the marker was never created, see README)",
        )
    return MountCheckResult(True, "mount marker present")
