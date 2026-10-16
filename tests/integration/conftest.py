"""Fixtures for tests against a real Dovecot (tests/integration/docker-compose.yml).

Skipped when nothing listens on LEVELKEEPER_IT_IMAP_PORT (default 14300).
"""

from __future__ import annotations

import imaplib
import os
import socket
import uuid
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from levelkeeper.imap_client import ImapClient

HOST = os.environ.get("LEVELKEEPER_IT_IMAP_HOST", "127.0.0.1")
PORT = int(os.environ.get("LEVELKEEPER_IT_IMAP_PORT", "14300"))
PASSWORD = "pass"
BASE_DATE = datetime(2024, 1, 1, tzinfo=UTC)


def pytest_collection_modifyitems(items):
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def server():
    try:
        socket.create_connection((HOST, PORT), timeout=2).close()
    except OSError:
        pytest.skip(f"no IMAP server on {HOST}:{PORT} (docker compose up in tests/integration)")
    return HOST, PORT


@pytest.fixture
def user(server):
    """Fresh mailbox per test: the server accepts any user."""
    return f"it-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def admin(server, user):
    """Second connection to set up and mess with the mailbox behind the client's back."""
    conn = imaplib.IMAP4(*server)
    conn.login(user, PASSWORD)
    yield conn
    try:
        conn.logout()
    except Exception:
        pass


@pytest.fixture
def imap_config(server, user, monkeypatch):
    # the client always speaks TLS, the test server is plain
    monkeypatch.setattr(imaplib, "IMAP4_SSL", lambda host, port: imaplib.IMAP4(host, port))
    return {"host": server[0], "port": server[1], "user": user, "password": PASSWORD}


@pytest.fixture
def client(imap_config):
    c = ImapClient(
        imap_config["host"], imap_config["port"], imap_config["user"], imap_config["password"]
    )
    c.connect()
    yield c
    c.close()


def make_message(name: str, days: int = 0, pad: int = 400) -> bytes:
    date = format_datetime(BASE_DATE + timedelta(days=days))
    return (
        f"From: a@example.com\r\nTo: b@example.com\r\nSubject: {name}\r\n"
        f"Date: {date}\r\nMessage-ID: <{name}@it>\r\n\r\n" + "x" * pad + "\r\n"
    ).encode()


def append(admin: imaplib.IMAP4, folder: str, name: str, days: int = 0, pad: int = 400) -> None:
    typ, data = admin.append(f'"{folder}"', None, None, make_message(name, days, pad))
    assert typ == "OK", data


def message_ids(admin: imaplib.IMAP4, folder: str) -> list[str]:
    """Message-IDs currently in a folder, flagged-deleted ones included."""
    typ, _ = admin.select(f'"{folder}"')
    assert typ == "OK"
    typ, data = admin.uid("search", None, "ALL")
    uids = data[0].split()
    if not uids:
        return []
    typ, data = admin.uid(
        "fetch", b",".join(uids).decode(), "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])"
    )
    return sorted(
        item[1].decode().split(":", 1)[1].strip() for item in data if isinstance(item, tuple)
    )
