"""Docker healthcheck: the last successful run must be recent."""

from __future__ import annotations

from datetime import UTC, datetime

from levelkeeper.state import StateStore

# a run may take longer than one interval, so allow a few misses
MISSED_INTERVALS = 3


def check_health(
    state_path: str, interval_seconds: float | None, now: datetime | None = None
) -> tuple[bool, str]:
    if interval_seconds is None:
        return True, "no run_interval, nothing to check"
    last = StateStore(state_path).last_success()
    if last is None:
        return False, "no successful run recorded yet"
    age = ((now or datetime.now(UTC)) - last).total_seconds()
    limit = interval_seconds * MISSED_INTERVALS
    if age > limit:
        return False, f"last successful run {age:.0f}s ago (limit {limit:.0f}s)"
    return True, f"last successful run {age:.0f}s ago"
