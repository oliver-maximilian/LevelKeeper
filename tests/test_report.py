from levelkeeper.report import error_mail_body, format_bytes, monthly_report_body
from levelkeeper.state import MonthStats


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1024**3) == "1.00 GB"


def test_monthly_report_body_contains_key_figures():
    stats = MonthStats(archived_count=5, archived_bytes=1024**2, errors=["oops"])
    body = monthly_report_body("2026-06", stats, fill_bytes=1024**3, quota_bytes=2 * 1024**3)
    assert "2026-06" in body
    assert "5" in body
    assert "50.0%" in body
    assert "oops" in body


def test_error_mail_body_includes_context():
    body = error_mail_body("something broke", {"folder": "INBOX"})
    assert "something broke" in body
    assert "folder: INBOX" in body
