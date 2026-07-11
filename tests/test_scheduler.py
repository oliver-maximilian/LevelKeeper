import pytest

from levelkeeper.scheduler import parse_interval, run_forever


def test_parse_interval_empty_is_none():
    assert parse_interval("") is None
    assert parse_interval("   ") is None


def test_parse_interval_units():
    assert parse_interval("30") == 30
    assert parse_interval("30s") == 30
    assert parse_interval("5m") == 300
    assert parse_interval("2h") == 7200
    assert parse_interval("1d") == 86400


def test_parse_interval_invalid():
    with pytest.raises(ValueError):
        parse_interval("abc")


def test_run_forever_stops_and_continues_after_error():
    count = {"n": 0}
    calls = []

    def run_once():
        count["n"] += 1
        calls.append(count["n"])
        if count["n"] == 1:
            raise RuntimeError("boom")

    def should_stop():
        return count["n"] >= 2

    run_forever(run_once, 0.01, should_stop)
    assert calls == [1, 2]
