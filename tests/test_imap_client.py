import pytest

from levelkeeper.imap_client import (
    FolderInfo,
    ImapClient,
    ImapError,
    UidValidityChanged,
    _parse_list_line,
    decode_modified_utf7,
    folder_display_path,
)


def test_decode_modified_utf7_plain_ascii():
    assert decode_modified_utf7("INBOX") == "INBOX"


def test_decode_modified_utf7_escaped_ampersand():
    assert decode_modified_utf7("Cars&-Bikes") == "Cars&Bikes"


def test_decode_modified_utf7_umlaut():
    assert decode_modified_utf7("Pers&APY-nlich") == "Persönlich"


def test_parse_list_line_quoted():
    line = b'(\\HasNoChildren) "/" "INBOX/Sent"'
    delim, name = _parse_list_line(line)
    assert delim == "/"
    assert name == "INBOX/Sent"


def test_parse_list_line_atom():
    line = b'(\\HasNoChildren) "." INBOX'
    delim, name = _parse_list_line(line)
    assert delim == "."
    assert name == "INBOX"


def test_folder_display_path_normalizes_delimiter():
    assert folder_display_path("INBOX.Projects.Foo", ".") == "INBOX/Projects/Foo"


class FakeImaplib:
    """imaplib stand-in, records commands."""

    def __init__(self, validities, caps=b"IMAP4REV1 UIDPLUS"):
        self.validities = list(validities)
        self.caps = caps
        self.commands = []

    def capability(self):
        return "OK", [self.caps]

    def select(self, mailbox, readonly=False):
        self._current = self.validities.pop(0)
        return "OK", [b"1"]

    def response(self, code):
        return code, [self._current]

    def uid(self, command, *args):
        self.commands.append((command, *args))
        return "OK", [b""]


def _client(fake):
    client = ImapClient("h", 993, "u", "p")
    client._imap = fake
    client._uidplus = b"UIDPLUS" in fake.caps
    return client


FOLDER = FolderInfo(raw_name="INBOX", display_name="INBOX", delimiter="/")


def test_uid_expunge_used_instead_of_plain_expunge():
    fake = FakeImaplib([b"7"])
    _client(fake).delete_message(FOLDER, "42", "7")
    assert fake.commands == [("store", "42", "+FLAGS", "(\\Deleted)"), ("expunge", "42")]


def test_delete_refused_when_uidvalidity_changed():
    fake = FakeImaplib([b"8"])
    with pytest.raises(UidValidityChanged):
        _client(fake).delete_message(FOLDER, "42", "7")
    assert fake.commands == []


def test_fetch_refused_when_uidvalidity_changed():
    fake = FakeImaplib([b"8"])
    with pytest.raises(UidValidityChanged):
        _client(fake).fetch_full_message(FOLDER, "42", "7")


def test_delete_refused_without_uidplus():
    fake = FakeImaplib([b"7"], caps=b"IMAP4REV1")
    with pytest.raises(ImapError):
        _client(fake).delete_message(FOLDER, "42", "7")
    assert fake.commands == []
