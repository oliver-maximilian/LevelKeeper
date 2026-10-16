"""NAS mount check via marker file.

A bind mount looks mounted in the container even if the host failed to mount
the share (Docker binds the empty local dir), so os.path.ismount() is not
enough. The marker exists only on the real share (created once, see setup.md).
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
