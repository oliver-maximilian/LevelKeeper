from datetime import UTC, datetime, timedelta

from levelkeeper.archiver import Archiver
from levelkeeper.config import Config
from levelkeeper.imap_client import FolderInfo, ImapError, MessageHeader
from levelkeeper.state import StateStore
from levelkeeper.storage import build_archive_path, write_eml_atomic

INBOX = FolderInfo(raw_name="INBOX", display_name="INBOX", delimiter="/")
TRASH = FolderInfo(raw_name="Trash", display_name="Trash", delimiter="/")

BASE_DATE = datetime(2024, 1, 1, tzinfo=UTC)


class FakeImapClient:
    def __init__(self, data: dict[FolderInfo, list[dict]]) -> None:
        self._data = data
        self.deleted: list[tuple[str, str]] = []
        self.fetch_calls: list[tuple[str, str]] = []
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.connected = False

    def list_folders(self) -> list[FolderInfo]:
        return list(self._data.keys())

    def message_headers(self, folder: FolderInfo) -> list[MessageHeader]:
        return [
            MessageHeader(
                folder=folder,
                uid=m["uid"],
                size=m["size"],
                date=m["date"],
                message_id=m["message_id"],
            )
            for m in self._data[folder]
        ]

    def fetch_full_message(self, folder: FolderInfo, uid: str) -> bytes:
        self.fetch_calls.append((folder.display_name, uid))
        for m in self._data[folder]:
            if m["uid"] == uid:
                return m["body"]
        raise ImapError(f"uid {uid} not found")

    def delete_message(self, folder: FolderInfo, uid: str) -> None:
        self.deleted.append((folder.display_name, uid))


class FakeNotifier:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.reports: list[tuple[str, str]] = []

    def send_error(self, subject: str, body: str) -> None:
        self.errors.append((subject, body))

    def send_report(self, subject: str, body: str) -> None:
        self.reports.append((subject, body))


def _msg(uid: str, size: int, days: int, body: bytes | None = None) -> dict:
    return {
        "uid": uid,
        "size": size,
        "date": BASE_DATE + timedelta(days=days),
        "message_id": f"<{uid}@test>",
        "body": body if body is not None else f"body-{uid}".encode(),
    }


def _cfg(tmp_path, quota: str, trigger: str, target: str, exclude=None) -> Config:
    archive_root = tmp_path / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    (archive_root / ".marker").touch()
    cfg = Config(
        imap_host="imap.example.com",
        imap_user="u@example.com",
        imap_password="pw",
        smtp_host="smtp.example.com",
        smtp_user="u@example.com",
        smtp_password="pw",
        archive_root=str(archive_root),
        mount_marker=".marker",
        quota=quota,
        trigger=trigger,
        target=target,
        report_recipients=["me@example.com"],
        state_path=str(tmp_path / "state.json"),
        lock_file=str(tmp_path / "lk.lock"),
        exclude_folders=exclude or [],
    )
    cfg.resolve_and_validate()
    return cfg


def _run(cfg: Config, client: FakeImapClient):
    notifier = FakeNotifier()
    state = StateStore(cfg.state_path)
    archiver = Archiver(cfg, notifier, state, imap_client_factory=lambda: client)
    result = archiver.run()
    return result, notifier


def test_below_trigger_does_nothing(tmp_path):
    data = {INBOX: [_msg("1", 300, 0)]}
    client = FakeImapClient(data)
    cfg = _cfg(tmp_path, quota="1000", trigger="600", target="400")

    result, notifier = _run(cfg, client)

    assert result.archived_count == 0
    assert client.deleted == []
    assert notifier.errors == []


def test_cleanup_reaches_target(tmp_path):
    data = {INBOX: [_msg("1", 300, 0), _msg("2", 300, 1), _msg("3", 300, 2)]}
    client = FakeImapClient(data)
    cfg = _cfg(tmp_path, quota="1000", trigger="600", target="200")

    result, notifier = _run(cfg, client)

    assert result.archived_count == 3
    assert result.fill_after == 0
    assert client.deleted == [("INBOX", "1"), ("INBOX", "2"), ("INBOX", "3")]
    assert notifier.errors == []
    for offset, uid in enumerate(("1", "2", "3")):
        date = BASE_DATE + timedelta(days=offset)
        path = build_archive_path(
            cfg.archive_root, "INBOX", date, f"<{uid}@test>", f"body-{uid}".encode()
        )
        assert path.exists()


def test_excluded_folder_counts_toward_fill_but_is_never_touched(tmp_path):
    data = {
        INBOX: [_msg("1", 300, 0)],
        TRASH: [_msg("2", 500, 0)],
    }
    client = FakeImapClient(data)
    cfg = _cfg(tmp_path, quota="1000", trigger="600", target="400", exclude=["Trash"])

    result, notifier = _run(cfg, client)

    assert result.fill_before == 800
    assert client.deleted == [("INBOX", "1")]
    assert result.archived_count == 1
    # Target of 400 can't be reached because the 500-byte Trash message is excluded.
    assert result.fill_after == 500
    assert any("Zielwert nicht erreichbar" in subject for subject, _ in notifier.errors)


def test_dry_run_writes_and_deletes_nothing(tmp_path):
    data = {INBOX: [_msg("1", 300, 0), _msg("2", 300, 1), _msg("3", 300, 2)]}
    client = FakeImapClient(data)
    cfg = _cfg(tmp_path, quota="1000", trigger="600", target="200")
    cfg.dry_run = True

    result, notifier = _run(cfg, client)

    assert result.archived_count == 3
    assert client.deleted == []
    written_emls = list((tmp_path / "archive").rglob("*.eml"))
    assert written_emls == []


def test_archive_conflict_aborts_run_and_leaves_mail_on_server(tmp_path):
    data = {INBOX: [_msg("1", 300, 0), _msg("2", 300, 1), _msg("3", 300, 2)]}
    client = FakeImapClient(data)
    cfg = _cfg(tmp_path, quota="1000", trigger="600", target="200")

    conflicting_path = build_archive_path(
        cfg.archive_root, "INBOX", BASE_DATE, "<1@test>", b"body-1"
    )
    write_eml_atomic(conflicting_path, b"unrelated pre-existing content")

    result, notifier = _run(cfg, client)

    assert result.aborted
    assert client.deleted == []
    assert client.fetch_calls == [("INBOX", "1")]
    assert any("Konflikt" in subject for subject, _ in notifier.errors)


def test_idempotent_restart_skips_rewrite_but_still_deletes(tmp_path):
    data = {INBOX: [_msg("1", 300, 0), _msg("2", 300, 1), _msg("3", 300, 2)]}
    client = FakeImapClient(data)
    cfg = _cfg(tmp_path, quota="1000", trigger="600", target="200")

    # Simulate a prior run that wrote msg 1 to the archive but crashed before
    # deleting it from the server.
    path = build_archive_path(cfg.archive_root, "INBOX", BASE_DATE, "<1@test>", b"body-1")
    write_eml_atomic(path, b"body-1")
    mtime_before = path.stat().st_mtime_ns

    result, notifier = _run(cfg, client)

    assert path.stat().st_mtime_ns == mtime_before
    assert client.deleted == [("INBOX", "1"), ("INBOX", "2"), ("INBOX", "3")]
    assert result.archived_count == 3
    assert notifier.errors == []
