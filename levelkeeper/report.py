"""Plain-text bodies for the monthly report and error notifications."""

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
        f"LevelKeeper Monatsbericht fuer {month_key}",
        "",
        f"Archivierte Mails:        {stats.archived_count}",
        f"Freigegebener Speicher:   {format_bytes(stats.archived_bytes)}",
        "",
        f"Aktueller Fuellstand:     {format_bytes(fill_bytes)} von "
        f"{format_bytes(quota_bytes)} ({pct:.1f}%)",
    ]
    if stats.errors:
        lines.append("")
        lines.append(f"Fehler/Warnungen im Berichtszeitraum ({len(stats.errors)}):")
        lines.extend(f"  - {err}" for err in stats.errors)
    return "\n".join(lines)


def error_mail_body(reason: str, context: dict[str, str] | None = None) -> str:
    lines = [
        "LevelKeeper hat ein kritisches Problem festgestellt und den Lauf abgebrochen.",
        "",
        reason,
    ]
    if context:
        lines.append("")
        lines.append("Details:")
        lines.extend(f"  {key}: {value}" for key, value in context.items())
    return "\n".join(lines)
