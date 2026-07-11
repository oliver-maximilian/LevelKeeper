"""Configuration loading, size/threshold parsing and validation.

Config comes from a TOML file (optional) with ENV variables layered on top,
so credentials can be kept out of the file entirely if desired. Sizes are
interpreted as binary multiples (1 GB == 1024**3 bytes) - see README.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_SIZE_UNITS = {
    "B": 1,
    "KB": 1024,
    "KIB": 1024,
    "MB": 1024**2,
    "MIB": 1024**2,
    "GB": 1024**3,
    "GIB": 1024**3,
    "TB": 1024**4,
    "TIB": 1024**4,
}


class ConfigError(ValueError):
    """Raised for invalid or missing configuration."""


def parse_size(value: str | int | float) -> int:
    """Parse a human size string ("1.5GB", "2048", "500MB") into bytes."""
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        raise ConfigError("empty size value")
    number_part = text.rstrip("aAbBiIkKmMgGtT")
    unit_part = text[len(number_part):].strip().upper() or "B"
    number_part = number_part.strip()
    if unit_part not in _SIZE_UNITS:
        raise ConfigError(f"unknown size unit in {value!r}")
    try:
        number = float(number_part)
    except ValueError as exc:
        raise ConfigError(f"invalid size value {value!r}") from exc
    return int(number * _SIZE_UNITS[unit_part])


def parse_threshold(value: str | int | float, quota_bytes: int) -> int:
    """Parse an absolute size or a percentage (of quota_bytes) into bytes."""
    text = str(value).strip()
    if text.endswith("%"):
        try:
            pct = float(text[:-1].strip())
        except ValueError as exc:
            raise ConfigError(f"invalid percentage value {value!r}") from exc
        return int(quota_bytes * pct / 100.0)
    return parse_size(value)


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # IMAP
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""

    # SMTP (notifications)
    smtp_host: str = "smtp.strato.de"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_addr: str = ""

    # Thresholds (raw config strings, resolved to bytes after quota is known)
    quota: str = ""
    trigger: str = ""
    target: str = ""

    # Archive
    archive_root: str = ""
    exclude_folders: list[str] = field(default_factory=lambda: ["Trash", "Junk", "Drafts"])
    max_message_size: str = "25MB"
    mount_marker: str = ".levelkeeper_mounted"

    # Notifications
    report_recipients: list[str] = field(default_factory=list)
    error_recipients: list[str] = field(default_factory=list)

    # Runtime / ops
    log_level: str = "INFO"
    log_format: str = "text"
    dry_run: bool = False
    run_interval: str = ""  # empty => run once and exit
    state_path: str = "/data/state.json"
    lock_file: str = "/data/levelkeeper.lock"

    # Resolved at validation time (bytes)
    quota_bytes: int = 0
    trigger_bytes: int = 0
    target_bytes: int = 0
    max_message_size_bytes: int = 0

    def resolve_and_validate(self) -> None:
        if not self.imap_host or not self.imap_user or not self.imap_password:
            raise ConfigError("imap_host, imap_user and imap_password are required")
        if not self.smtp_host or not self.smtp_user or not self.smtp_password:
            raise ConfigError("smtp_host, smtp_user and smtp_password are required")
        if not self.archive_root:
            raise ConfigError("archive_root is required")
        if not self.quota:
            raise ConfigError("quota is required")
        if not self.report_recipients and not self.error_recipients:
            raise ConfigError("at least one of report_recipients/error_recipients is required")

        self.quota_bytes = parse_size(self.quota)
        self.trigger_bytes = parse_threshold(self.trigger, self.quota_bytes)
        self.target_bytes = parse_threshold(self.target, self.quota_bytes)
        self.max_message_size_bytes = parse_size(self.max_message_size)

        if not self.smtp_from_addr:
            self.smtp_from_addr = self.smtp_user
        if not self.error_recipients:
            self.error_recipients = list(self.report_recipients)
        if not self.report_recipients:
            self.report_recipients = list(self.error_recipients)

        if self.target_bytes >= self.trigger_bytes:
            raise ConfigError(
                "target must be strictly lower than trigger "
                f"(target={self.target_bytes} bytes, trigger={self.trigger_bytes} bytes)"
            )
        if self.trigger_bytes > self.quota_bytes:
            raise ConfigError(
                f"trigger ({self.trigger_bytes} bytes) exceeds quota ({self.quota_bytes} bytes)"
            )


_ENV_PREFIX = "LEVELKEEPER_"


def _apply_env_overrides(cfg: Config) -> None:
    env = os.environ

    def get(name: str) -> str | None:
        return env.get(_ENV_PREFIX + name)

    if v := get("IMAP_HOST"):
        cfg.imap_host = v
    if v := get("IMAP_PORT"):
        cfg.imap_port = int(v)
    if v := get("IMAP_USER"):
        cfg.imap_user = v
    if v := get("IMAP_PASSWORD"):
        cfg.imap_password = v

    if v := get("SMTP_HOST"):
        cfg.smtp_host = v
    if v := get("SMTP_PORT"):
        cfg.smtp_port = int(v)
    if v := get("SMTP_USER"):
        cfg.smtp_user = v
    if v := get("SMTP_PASSWORD"):
        cfg.smtp_password = v
    if v := get("SMTP_FROM_ADDR"):
        cfg.smtp_from_addr = v

    if v := get("QUOTA"):
        cfg.quota = v
    if v := get("TRIGGER"):
        cfg.trigger = v
    if v := get("TARGET"):
        cfg.target = v

    if v := get("ARCHIVE_ROOT"):
        cfg.archive_root = v
    if v := get("EXCLUDE_FOLDERS"):
        cfg.exclude_folders = _split_list(v)
    if v := get("MAX_MESSAGE_SIZE"):
        cfg.max_message_size = v
    if v := get("MOUNT_MARKER"):
        cfg.mount_marker = v

    if v := get("REPORT_RECIPIENTS"):
        cfg.report_recipients = _split_list(v)
    if v := get("ERROR_RECIPIENTS"):
        cfg.error_recipients = _split_list(v)

    if v := get("LOG_LEVEL"):
        cfg.log_level = v
    if v := get("LOG_FORMAT"):
        cfg.log_format = v
    if v := get("DRY_RUN"):
        cfg.dry_run = _env_bool(v)
    if v := get("RUN_INTERVAL"):
        cfg.run_interval = v
    if v := get("STATE_PATH"):
        cfg.state_path = v
    if v := get("LOCK_FILE"):
        cfg.lock_file = v


def _apply_toml(cfg: Config, data: dict) -> None:
    imap = data.get("imap", {})
    cfg.imap_host = imap.get("host", cfg.imap_host)
    cfg.imap_port = imap.get("port", cfg.imap_port)
    cfg.imap_user = imap.get("user", cfg.imap_user)
    cfg.imap_password = imap.get("password", cfg.imap_password)

    smtp = data.get("smtp", {})
    cfg.smtp_host = smtp.get("host", cfg.smtp_host)
    cfg.smtp_port = smtp.get("port", cfg.smtp_port)
    cfg.smtp_user = smtp.get("user", cfg.smtp_user)
    cfg.smtp_password = smtp.get("password", cfg.smtp_password)
    cfg.smtp_from_addr = smtp.get("from_addr", cfg.smtp_from_addr)

    quota = data.get("quota", {})
    cfg.quota = str(quota.get("quota", cfg.quota))
    cfg.trigger = str(quota.get("trigger", cfg.trigger))
    cfg.target = str(quota.get("target", cfg.target))

    archive = data.get("archive", {})
    cfg.archive_root = archive.get("root", cfg.archive_root)
    cfg.exclude_folders = archive.get("exclude_folders", cfg.exclude_folders)
    cfg.max_message_size = str(archive.get("max_message_size", cfg.max_message_size))
    cfg.mount_marker = archive.get("mount_marker", cfg.mount_marker)

    notify = data.get("notify", {})
    cfg.report_recipients = notify.get("report_recipients", cfg.report_recipients)
    cfg.error_recipients = notify.get("error_recipients", cfg.error_recipients)

    runtime = data.get("runtime", {})
    cfg.log_level = runtime.get("log_level", cfg.log_level)
    cfg.log_format = runtime.get("log_format", cfg.log_format)
    cfg.dry_run = runtime.get("dry_run", cfg.dry_run)
    cfg.run_interval = str(runtime.get("run_interval", cfg.run_interval))
    cfg.state_path = runtime.get("state_path", cfg.state_path)
    cfg.lock_file = runtime.get("lock_file", cfg.lock_file)


def load_config(path: str | Path | None) -> Config:
    """Load config from an optional TOML file, then apply ENV overrides."""
    cfg = Config()
    if path is not None and Path(path).is_file():
        with open(path, "rb") as f:
            data = tomllib.load(f)
        _apply_toml(cfg, data)
    _apply_env_overrides(cfg)
    cfg.resolve_and_validate()
    return cfg
