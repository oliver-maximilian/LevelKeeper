from datetime import UTC, datetime

from levelkeeper.storage import (
    build_archive_path,
    build_filename,
    build_relative_dir,
    find_existing_archive,
    sanitize_path_segment,
    verify_written,
    write_eml_atomic,
)


def test_sanitize_path_segment():
    assert sanitize_path_segment("Projects/Foo") == "Projects_Foo"
    assert sanitize_path_segment("  trailing.dot.  ") == "trailing.dot"
    assert sanitize_path_segment("") == "_"


def test_build_relative_dir():
    dt = datetime(2024, 3, 15, tzinfo=UTC)
    rel = build_relative_dir("INBOX/Projects", dt)
    assert str(rel) == "2024/INBOX/Projects"


def test_build_filename_deterministic():
    dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=UTC)
    raw = b"Subject: test\r\n\r\nbody"
    name1 = build_filename(dt, "<abc@example.com>", raw)
    name2 = build_filename(dt, "<abc@example.com>", raw)
    assert name1 == name2
    assert name1.startswith("2024-03-15_103000_")
    assert name1.endswith(".eml")


def test_build_filename_fallback_without_message_id():
    dt = datetime(2024, 3, 15, tzinfo=UTC)
    name_a = build_filename(dt, "", b"body a")
    name_b = build_filename(dt, "", b"body b")
    assert name_a != name_b


def test_write_and_verify_roundtrip(tmp_path):
    path = tmp_path / "sub" / "msg.eml"
    raw = b"hello world"
    write_eml_atomic(path, raw)
    assert path.read_bytes() == raw
    assert verify_written(path, raw).ok


def test_verify_written_detects_mismatch(tmp_path):
    path = tmp_path / "msg.eml"
    write_eml_atomic(path, b"original")
    assert not verify_written(path, b"different content").ok


def test_find_existing_archive_none_when_absent(tmp_path):
    assert find_existing_archive(tmp_path / "missing.eml", b"data") is None


def test_find_existing_archive_matches_identical(tmp_path):
    path = tmp_path / "msg.eml"
    raw = b"same bytes"
    write_eml_atomic(path, raw)
    result = find_existing_archive(path, raw)
    assert result is not None and result.ok


def test_find_existing_archive_conflict(tmp_path):
    path = tmp_path / "msg.eml"
    write_eml_atomic(path, b"old content")
    result = find_existing_archive(path, b"new content")
    assert result is not None and not result.ok


def test_build_archive_path_full(tmp_path):
    dt = datetime(2023, 1, 1, tzinfo=UTC)
    path = build_archive_path(tmp_path, "INBOX", dt, "<id@example.com>", b"body")
    assert path.parent == tmp_path / "2023" / "INBOX"
    assert path.suffix == ".eml"
