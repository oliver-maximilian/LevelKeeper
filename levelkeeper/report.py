"""Mail bodies."""

from __future__ import annotations

from levelkeeper.state import MonthStats

_UNITS = ["B", "KB", "MB", "GB", "TB"]


def format_bytes(n: int) -> str:
    value = float(n)
    for unit in _UNITS:
        if unit == "B":
            if value < 1024:
                return f"{int(value)} {unit}"
        elif value < 1024 or unit == _UNITS[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} {_UNITS[-1]}"


def monthly_report_body(
    month_key: str, stats: MonthStats, fill_bytes: int, quota_bytes: int
) -> str:
    pct = (fill_bytes / quota_bytes * 100) if quota_bytes else 0.0
    lines = [
        f"LevelKeeper Monthly report for {month_key}",
        "",
        f"Archived mails:          {stats.archived_count}",
        f"Freed storage:           {format_bytes(stats.archived_bytes)}",
        "",
        f"Current fill level:     {format_bytes(fill_bytes)} of "
        f"{format_bytes(quota_bytes)} ({pct:.1f}%)",
    ]
    if stats.errors:
        lines.append("")
        lines.append(f"Errors/warnings in the period ({len(stats.errors)}):")
        lines.extend(f"  - {err}" for err in stats.errors)
    return "\n".join(lines)


def error_mail_body(reason: str, context: dict[str, str] | None = None) -> str:
    lines = [
        "LevelKeeper hit a critical problem and aborted the run.",
        "",
        reason,
    ]
    if context:
        lines.append("")
        lines.append("Details:")
        lines.extend(f"  {key}: {value}" for key, value in context.items())
    return "\n".join(lines)
