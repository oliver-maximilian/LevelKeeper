"""SMTP mails."""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate

from levelkeeper.config import Config

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: Config) -> None:
        self.config = config

    def _send(self, subject: str, body: str, recipients: list[str]) -> bool:
        if not recipients:
            logger.warning("no recipients configured, skipping mail %r", subject)
            return False
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = self.config.smtp_from_addr
        msg["To"] = ", ".join(recipients)
        msg["Date"] = formatdate(localtime=True)
        try:
            with smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, timeout=30) as smtp:
                smtp.login(self.config.smtp_user, self.config.smtp_password)
                smtp.sendmail(self.config.smtp_from_addr, recipients, msg.as_string())
            logger.info("sent mail %r to %s", subject, recipients)
            return True
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("failed to send mail %r to %s: %s", subject, recipients, exc)
            return False

    def send_error(self, subject: str, body: str) -> bool:
        return self._send(f"[LevelKeeper] {subject}", body, self.config.error_recipients)

    def send_report(self, subject: str, body: str) -> bool:
        return self._send(f"[LevelKeeper] {subject}", body, self.config.report_recipients)
