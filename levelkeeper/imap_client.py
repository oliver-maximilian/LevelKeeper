"""Thin IMAP wrapper: folder listing, header enumeration, fetch and delete.

Everything that touches message identity is done via UID commands so that
sequence-number drift from an EXPUNGE mid-run never causes us to act on the
wrong message.
"""

from __future__ import annotations

import base64
import email
import email.utils
import imaplib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

_UID_RE = re.compile(rb"UID (\d+)")
_SIZE_RE = re.compile(rb"RFC822\.SIZE (\d+)")
_INTERNALDATE_RE = re.compile(rb'INTERNALDATE "([^"]+)"')
_LIST_RE = re.compile(rb'^\(([^)]*)\)\s+(NIL|"(?:[^"\\]|\\.)*")\s+(.+)$')

_FETCH_BATCH_SIZE = 300


class ImapError(RuntimeError):
    """Raised for any non-OK IMAP response."""


def decode_modified_utf7(text: str) -> str:
    """Decode IMAP modified UTF-7 (RFC 3501 5.1.3) into a normal str."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "&":
            j = text.find("-", i + 1)
            if j == -1:
                j = n
            chunk = text[i + 1 : j]
            if chunk == "":
                result.append("&")
            else:
                b64 = chunk.replace(",", "/")
                padded = b64 + "=" * (-len(b64) % 4)
                raw = base64.b64decode(padded)
                result.append(raw.decode("utf-16-be"))
            i = j + 1
        else:
            result.append(c)
            i += 1
    return "".join(result)


def _unquote(raw: bytes) -> str:
    inner = raw[1:-1]
    return inner.decode("ascii").replace('\\"', '"').replace("\\\\", "\\")


def _parse_list_line(line: bytes) -> tuple[str, str] | None:
    match = _LIST_RE.match(line)
    if not match:
        return None
    _flags, delim_raw, name_raw = match.groups()
    delimiter = "" if delim_raw == b"NIL" else _unquote(delim_raw)
    name = _unquote(name_raw) if name_raw.startswith(b'"') else name_raw.decode("ascii")
    return delimiter, name


def folder_display_path(raw_name: str, delimiter: str) -> str:
    """Human-readable, filesystem-friendly path for a raw IMAP mailbox name."""
    decoded = decode_modified_utf7(raw_name)
    if delimiter and delimiter != "/":
        decoded = decoded.replace(delimiter, "/")
    return decoded


def _quote_mailbox(raw_name: str) -> str:
    escaped = raw_name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _chunk(seq: list[str], size: int) -> list[list[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


@dataclass(frozen=True)
class FolderInfo:
    raw_name: str
    display_name: str
    delimiter: str


@dataclass(frozen=True)
class MessageHeader:
    folder: FolderInfo
    uid: str
    size: int
    date: datetime
    message_id: str


class ImapClient:
    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self._imap: imaplib.IMAP4_SSL | None = None
        self._selected: tuple[str, bool] | None = None

    def connect(self) -> None:
        self._imap = imaplib.IMAP4_SSL(self.host, self.port)
        typ, data = self._imap.login(self.user, self.password)
        if typ != "OK":
            raise ImapError(f"IMAP login failed: {data!r}")
        self._selected = None

    def close(self) -> None:
        if self._imap is None:
            return
        try:
            if self._selected is not None:
                self._imap.close()
        except Exception:
            pass
        try:
            self._imap.logout()
        except Exception:
            pass
        self._imap = None
        self._selected = None

    def __enter__(self) -> ImapClient:
        self.connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def _select_folder(self, folder: FolderInfo, readonly: bool) -> None:
        assert self._imap is not None
        want = (folder.raw_name, readonly)
        if self._selected == want:
            return
        quoted = _quote_mailbox(folder.raw_name)
        typ, data = self._imap.select(quoted, readonly=readonly)
        if typ != "OK":
            raise ImapError(f"SELECT {folder.display_name!r} failed: {data!r}")
        self._selected = want

    def list_folders(self) -> list[FolderInfo]:
        assert self._imap is not None
        typ, data = self._imap.list()
        if typ != "OK":
            raise ImapError(f"LIST failed: {data!r}")
        folders = []
        for line in data:
            if line is None:
                continue
            parsed = _parse_list_line(line)
            if parsed is None:
                logger.warning("could not parse LIST response line: %r", line)
                continue
            delimiter, raw_name = parsed
            folders.append(
                FolderInfo(
                    raw_name=raw_name,
                    display_name=folder_display_path(raw_name, delimiter),
                    delimiter=delimiter,
                )
            )
        return folders

    def message_headers(self, folder: FolderInfo) -> list[MessageHeader]:
        """Enumerate every message in a folder with size/date/message-id.

        Uses BODY.PEEK so the \\Seen flag is never touched.
        """
        assert self._imap is not None
        self._select_folder(folder, readonly=True)
        typ, data = self._imap.uid("search", None, "ALL")
        if typ != "OK":
            raise ImapError(f"SEARCH failed in {folder.display_name!r}: {data!r}")
        uids = data[0].split() if data and data[0] else []
        if not uids:
            return []
        uids = [u.decode() for u in uids]

        headers: list[MessageHeader] = []
        for batch in _chunk(uids, _FETCH_BATCH_SIZE):
            typ, data = self._imap.uid(
                "fetch",
                ",".join(batch),
                "(UID INTERNALDATE RFC822.SIZE BODY.PEEK[HEADER.FIELDS (DATE MESSAGE-ID)])",
            )
            if typ != "OK":
                raise ImapError(f"FETCH failed in {folder.display_name!r}: {data!r}")
            for item in data:
                if not isinstance(item, tuple):
                    continue
                info, literal = item
                headers.append(self._parse_header_item(folder, info, literal))
        return headers

    def _parse_header_item(self, folder: FolderInfo, info: bytes, literal: bytes) -> MessageHeader:
        uid_match = _UID_RE.search(info)
        size_match = _SIZE_RE.search(info)
        internaldate_match = _INTERNALDATE_RE.search(info)
        uid = uid_match.group(1).decode() if uid_match else ""
        size = int(size_match.group(1)) if size_match else 0

        msg = email.message_from_bytes(literal)
        message_id = (msg.get("Message-ID") or "").strip()
        date_header = msg.get("Date")
        dt: datetime | None = None
        if date_header:
            try:
                dt = email.utils.parsedate_to_datetime(date_header)
            except (TypeError, ValueError):
                dt = None
        if dt is None and internaldate_match:
            try:
                dt = datetime.strptime(internaldate_match.group(1).decode(), "%d-%b-%Y %H:%M:%S %z")
            except ValueError:
                dt = None
        if dt is None:
            dt = datetime.now(UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        return MessageHeader(folder=folder, uid=uid, size=size, date=dt, message_id=message_id)

    def fetch_full_message(self, folder: FolderInfo, uid: str) -> bytes:
        assert self._imap is not None
        self._select_folder(folder, readonly=True)
        typ, data = self._imap.uid("fetch", uid, "(RFC822)")
        if typ != "OK" or not data or data[0] is None:
            raise ImapError(
                f"FETCH RFC822 failed for uid={uid} in {folder.display_name!r}: {data!r}"
            )
        for item in data:
            if isinstance(item, tuple):
                return item[1]
        raise ImapError(f"no message body returned for uid={uid} in {folder.display_name!r}")

    def delete_message(self, folder: FolderInfo, uid: str) -> None:
        assert self._imap is not None
        self._select_folder(folder, readonly=False)
        typ, data = self._imap.uid("store", uid, "+FLAGS", "(\\Deleted)")
        if typ != "OK":
            raise ImapError(f"STORE +FLAGS \\Deleted failed for uid={uid}: {data!r}")
        typ, data = self._imap.expunge()
        if typ != "OK":
            raise ImapError(f"EXPUNGE failed in {folder.display_name!r}: {data!r}")
