import time

import pytest

from levelkeeper.archiver import Archiver
from levelkeeper.config import Config
from levelkeeper.imap_client import ImapError, UidValidityChanged
from levelkeeper.state import StateStore
from tests.integration.conftest import append, message_ids


def _folder(client, display_name):
    return next(f for f in client.list_folders() if f.display_name == display_name)


def _validity(admin, folder):
    admin.select(f'"{folder}"')
    return admin.response("UIDVALIDITY")[1][0].decode()


class RecordingNotifier:
    def __init__(self):
        self.errors = []

    def send_error(self, subject, body):
        self.errors.append((subject, body))
        return True

    def send_report(self, subject, body):
        return True


def test_server_advertises_uidplus(client):
    assert client._uidplus


def test_modified_utf7_folder_names_are_decoded(client, admin):
    assert admin.create('"Pers&APY-nlich"')[0] == "OK"
    assert admin.create('"Archiv/Gesch&AOQ-ft"')[0] == "OK"

    names = {f.display_name for f in client.list_folders()}

    assert {"INBOX", "Persönlich", "Archiv/Geschäft"} <= names


def test_header_scan_returns_size_date_id_and_uidvalidity(client, admin):
    append(admin, "INBOX", "m1", days=3)

    headers = client.message_headers(_folder(client, "INBOX"))

    assert len(headers) == 1
    h = headers[0]
    assert h.message_id == "<m1@it>"
    assert h.size > 400
    assert h.date.year == 2024 and h.date.day == 4
    assert h.uidvalidity == _validity(admin, "INBOX")


def test_delete_removes_only_the_target_even_if_others_are_flagged_deleted(client, admin):
    for name in ("a", "b", "c"):
        append(admin, "INBOX", name)
    inbox = _folder(client, "INBOX")
    headers = {h.message_id: h for h in client.message_headers(inbox)}

    # the user flagged b in the mail client but never expunged
    admin.select("INBOX")
    admin.uid("store", headers["<b@it>"].uid, "+FLAGS", "(\\Deleted)")

    client.delete_message(inbox, headers["<a@it>"].uid, headers["<a@it>"].uidvalidity)

    assert message_ids(admin, "INBOX") == ["<b@it>", "<c@it>"]


def test_fetch_returns_exact_bytes(client, admin):
    append(admin, "INBOX", "raw")
    inbox = _folder(client, "INBOX")
    h = client.message_headers(inbox)[0]

    raw = client.fetch_full_message(inbox, h.uid, h.uidvalidity)

    assert len(raw) == h.size
    assert b"Message-ID: <raw@it>" in raw


def test_rebuilt_folder_is_detected_and_nothing_is_deleted(client, admin):
    admin.create("Target")
    append(admin, "Target", "old")
    target = _folder(client, "Target")
    old = client.message_headers(target)[0]
    client.message_headers(_folder(client, "INBOX"))  # leaves another folder selected

    # server rebuilds the folder: same UID, new content, new UIDVALIDITY
    time.sleep(1.1)
    admin.delete("Target")
    admin.create("Target")
    append(admin, "Target", "new")
    assert _validity(admin, "Target") != old.uidvalidity

    with pytest.raises(UidValidityChanged):
        client.fetch_full_message(target, old.uid, old.uidvalidity)
    with pytest.raises(UidValidityChanged):
        client.delete_message(target, old.uid, old.uidvalidity)

    assert message_ids(admin, "Target") == ["<new@it>"]


def test_delete_unknown_uid_does_not_touch_other_mail(client, admin):
    append(admin, "INBOX", "keep")
    inbox = _folder(client, "INBOX")
    h = client.message_headers(inbox)[0]

    try:
        client.delete_message(inbox, "99999", h.uidvalidity)
    except ImapError:
        pass

    assert message_ids(admin, "INBOX") == ["<keep@it>"]


def test_full_run_archives_oldest_first_and_deletes_after_verification(
    tmp_path, imap_config, admin
):
    admin.create('"Pers&APY-nlich"')
    for i in range(3):
        append(admin, "INBOX", f"inbox{i}", days=i * 2)
        append(admin, "Pers&APY-nlich", f"pers{i}", days=i * 2 + 1)

    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / ".marker").touch()
    cfg = Config(
        imap_host=imap_config["host"],
        imap_port=imap_config["port"],
        imap_user=imap_config["user"],
        imap_password=imap_config["password"],
        smtp_host="smtp.invalid",
        smtp_user="x",
        smtp_password="x",
        archive_root=str(archive),
        mount_marker=".marker",
        quota="5000",
        trigger="2500",
        target="1200",
        report_recipients=["me@example.com"],
        state_path=str(tmp_path / "state.json"),
        lock_file=str(tmp_path / "lk.lock"),
    )
    cfg.resolve_and_validate()
    notifier = RecordingNotifier()

    result = Archiver(cfg, notifier, StateStore(cfg.state_path)).run()

    assert not result.aborted
    assert notifier.errors == []
    assert result.fill_after <= cfg.target_bytes
    archived = sorted(p for p in archive.rglob("*.eml"))
    assert len(archived) == result.archived_count >= 4
    assert any("Persönlich" in p.parts for p in archived)
    # oldest two are gone from the server, the newest is still there
    remaining = message_ids(admin, "INBOX") + message_ids(admin, "Pers&APY-nlich")
    assert "<inbox0@it>" not in remaining
    assert "<pers2@it>" in remaining or "<inbox2@it>" in remaining
    assert len(remaining) + len(archived) == 6
