from datetime import date

from levelkeeper.state import StateStore


def test_record_run_accumulates(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.record_run(date(2026, 6, 15), 3, 1000, [])
    store.record_run(date(2026, 6, 20), 2, 500, ["oops"])

    reloaded = StateStore(path)
    stats = reloaded._data["months"]["2026-06"]
    assert stats["archived_count"] == 5
    assert stats["archived_bytes"] == 1500
    assert stats["errors"] == ["oops"]


def test_pending_monthly_report_only_on_first(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.record_run(date(2026, 6, 15), 1, 100, [])

    assert store.pending_monthly_report(date(2026, 6, 15)) is None

    pending = store.pending_monthly_report(date(2026, 7, 1))
    assert pending is not None
    month_key, stats = pending
    assert month_key == "2026-06"
    assert stats.had_activity()


def test_pending_monthly_report_skips_when_no_activity(tmp_path):
    store = StateStore(tmp_path / "state.json")
    pending = store.pending_monthly_report(date(2026, 7, 1))
    assert pending is not None
    _month_key, stats = pending
    assert stats is None


def test_mark_reported_prevents_resend(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.record_run(date(2026, 6, 15), 1, 100, [])
    store.mark_reported("2026-06")
    assert store.pending_monthly_report(date(2026, 7, 1)) is None
