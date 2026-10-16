from datetime import UTC, datetime, timedelta

from levelkeeper.health import check_health
from levelkeeper.state import StateStore

NOW = datetime(2026, 6, 1, 12, tzinfo=UTC)


def _state(tmp_path, last=None):
    path = tmp_path / "state.json"
    if last is not None:
        StateStore(path).mark_success(last)
    return str(path)


def test_no_interval_is_always_healthy(tmp_path):
    assert check_health(_state(tmp_path), None, NOW)[0]


def test_no_success_recorded_is_unhealthy(tmp_path):
    assert not check_health(_state(tmp_path), 3600, NOW)[0]


def test_recent_success_is_healthy(tmp_path):
    state = _state(tmp_path, NOW - timedelta(hours=2))
    assert check_health(state, 3600, NOW)[0]


def test_stale_success_is_unhealthy(tmp_path):
    state = _state(tmp_path, NOW - timedelta(hours=4))
    healthy, reason = check_health(state, 3600, NOW)
    assert not healthy
    assert "limit" in reason
