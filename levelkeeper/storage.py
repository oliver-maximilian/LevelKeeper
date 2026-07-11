"""Archive layout, atomic .eml writing and write verification.

Layout: <archive_root>/<year>/<imap-folder-path>/YYYY-MM-DD_HHMMSS_<hash>.eml

The filename is fully deterministic from the message itself (Message-ID, or
message body as a fallback), so re-processing the same message after a crash
always resolves to the same path - this is what makes idempotent restarts
possible (see find_existing_archive).
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_UNSAFE_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_path_segment(name: str) -> str:
    cleaned = _UNSAFE_CHARS_RE.sub("_", name).strip().rstrip(".")
    return cleaned or "_"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def message_hash(message_id: str, raw_bytes: bytes) -> str:
    """Short, stable identifier derived from Message-ID (or the body as fallback)."""
    basis = message_id.strip().encode("utf-8") if message_id.strip() else raw_bytes
    return hashlib.sha256(basis).hexdigest()[:16]


def build_relative_dir(folder_display_name: str, message_date: datetime) -> Path:
    segments = [sanitize_path_segment(p) for p in folder_display_name.split("/") if p]
    return Path(str(message_date.year), *segments)


def build_filename(message_date: datetime, message_id: str, raw_bytes: bytes) -> str:
    stamp = message_date.strftime("%Y-%m-%d_%H%M%S")
    return f"{stamp}_{message_hash(message_id, raw_bytes)}.eml"


def build_archive_path(
    archive_root: str | Path,
    folder_display_name: str,
    message_date: datetime,
    message_id: str,
    raw_bytes: bytes,
) -> Path:
    rel_dir = build_relative_dir(folder_display_name, message_date)
    filename = build_filename(message_date, message_id, raw_bytes)
    return Path(archive_root) / rel_dir / filename


@dataclass
class VerifyResult:
    ok: bool
    reason: str = ""


def find_existing_archive(path: Path, raw_bytes: bytes) -> VerifyResult | None:
    """Check whether `path` already holds this exact message (idempotent restart).

    Returns None if no file exists yet. Returns a VerifyResult if one does:
    ok=True means it's the same message already safely archived (write can be
    skipped); ok=False means an unexpected conflict was found on disk and the
    caller must treat this as a hard failure (do not delete from the server).
    """
    if not path.exists():
        return None
    existing = path.read_bytes()
    if sha256_hex(existing) == sha256_hex(raw_bytes):
        return VerifyResult(ok=True, reason="identical file already archived")
    return VerifyResult(
        ok=False,
        reason=f"archive path {path} already exists with different content (checksum mismatch)",
    )


def write_eml_atomic(path: Path, raw_bytes: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with open(tmp_path, "wb") as f:
        f.write(raw_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def verify_written(path: Path, raw_bytes: bytes) -> VerifyResult:
    try:
        on_disk = path.read_bytes()
    except OSError as exc:
        return VerifyResult(ok=False, reason=f"could not read back {path}: {exc}")
    if len(on_disk) != len(raw_bytes):
        return VerifyResult(
            ok=False,
            reason=f"size mismatch for {path}: expected {len(raw_bytes)}, got {len(on_disk)}",
        )
    if sha256_hex(on_disk) != sha256_hex(raw_bytes):
        return VerifyResult(ok=False, reason=f"checksum mismatch for {path}")
    return VerifyResult(ok=True)
