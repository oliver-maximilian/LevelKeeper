"""Small persistent JSON state file backing the monthly report.

Kept deliberately simple (stdlib json, one file) - this is not an archive
index, just enough bookkeeping to know what happened last month and whether
a report for it has already gone out.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def _previous_month_key(today: date) -> str:
    first_of_this_month = today.replace(day=1)
    last_day_prev_month = first_of_this_month - timedelta(days=1)
    return last_day_prev_month.strftime("%Y-%m")


@dataclass
class MonthStats:
    archived_count: int = 0
    archived_bytes: int = 0
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> MonthStats:
        return cls(
            archived_count=data.get("archived_count", 0),
            archived_bytes=data.get("archived_bytes", 0),
            errors=list(data.get("errors", [])),
        )

    def to_dict(self) -> dict:
        return {
            "archived_count": self.archived_count,
            "archived_bytes": self.archived_bytes,
            "errors": self.errors,
        }

    def had_activity(self) -> bool:
        return self.archived_count > 0 or bool(self.errors)


class StateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("could not read state file %s (%s), starting fresh", self.path, exc)
        return {"months": {}, "reported_through": None}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(f".{self.path.name}.tmp-{os.getpid()}")
        tmp_path.write_text(json.dumps(self._data, indent=2, sort_keys=True))
        os.replace(tmp_path, self.path)

    def record_run(
        self, when: date, archived_count: int, archived_bytes: int, errors: list[str]
    ) -> None:
        month_key = when.strftime("%Y-%m")
        months = self._data.setdefault("months", {})
        month = MonthStats.from_dict(months.get(month_key, {}))
        month.archived_count += archived_count
        month.archived_bytes += archived_bytes
        month.errors.extend(errors)
        months[month_key] = month.to_dict()
        self._save()

    def pending_monthly_report(self, today: date) -> tuple[str, MonthStats | None] | None:
        """(month_key, stats) for the previous month if a report is due today, else None."""
        if today.day != 1:
            return None
        prev_month = _previous_month_key(today)
        if self._data.get("reported_through") == prev_month:
            return None
        raw = self._data.get("months", {}).get(prev_month)
        stats = MonthStats.from_dict(raw) if raw is not None else None
        return prev_month, stats

    def mark_reported(self, month_key: str) -> None:
        self._data["reported_through"] = month_key
        self._save()
