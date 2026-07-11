import smtplib

from levelkeeper.config import Config
from levelkeeper.notifier import Notifier


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.login_args = None
        self.sendmail_args = None
        FakeSMTP.instances.append(self)

    def login(self, user, password):
        self.login_args = (user, password)

    def sendmail(self, from_addr, to_addrs, msg):
        self.sendmail_args = (from_addr, to_addrs, msg)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_send_error_uses_configured_smtp(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)

    cfg = Config(
        smtp_host="smtp.strato.de",
        smtp_port=465,
        smtp_user="me@example.com",
        smtp_password="pw",
        smtp_from_addr="me@example.com",
        error_recipients=["ops@example.com"],
    )
    Notifier(cfg).send_error("Test Subject", "Test Body")

    assert len(FakeSMTP.instances) == 1
    instance = FakeSMTP.instances[0]
    assert instance.login_args == ("me@example.com", "pw")
    from_addr, to_addrs, msg = instance.sendmail_args
    assert from_addr == "me@example.com"
    assert to_addrs == ["ops@example.com"]
    assert "[LevelKeeper] Test Subject" in msg


def test_send_skips_when_no_recipients(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)

    cfg = Config(
        smtp_host="smtp.strato.de",
        smtp_user="me@example.com",
        smtp_password="pw",
        smtp_from_addr="me@example.com",
        error_recipients=[],
    )
    Notifier(cfg).send_error("Subject", "Body")

    assert len(FakeSMTP.instances) == 0
