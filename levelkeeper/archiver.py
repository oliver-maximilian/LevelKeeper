"""Core run loop: fill-level check, oldest-first archiving, verified deletes.

Safety invariant enforced throughout: a message is only ever deleted from the
server after its .eml has been written to the archive AND verified (size +
SHA-256) against the bytes fetched from the server. Any failure along that
path aborts the whole run immediately and leaves the affected (and all
remaining) messages untouched on the server.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from levelkeeper.config import Config
from levelkeeper.imap_client import FolderInfo, ImapClient, ImapError, MessageHeader
from levelkeeper.lockfile import LockFile, LockHeldError
from levelkeeper.mount_check import check_mount
from levelkeeper.notifier import Notifier
from levelkeeper.report import error_mail_body, format_bytes, monthly_report_body
from levelkeeper.state import StateStore
from levelkeeper.storage import (
    build_archive_path,
    find_existing_archive,
    verify_written,
    write_eml_atomic,
)

logger = logging.getLogger(__name__)


class AbortRun(RuntimeError):
    """Internal signal that a run was aborted; details already logged/notified."""


@dataclass
class RunResult:
    started_at: datetime
    finished_at: datetime | None = None
    fill_before: int = 0
    fill_after: int = 0
    archived_count: int = 0
    archived_bytes: int = 0
    dry_run: bool = False
    aborted: bool = False
    abort_reason: str = ""
    skipped: bool = False
    action_taken: bool = False

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()


def _is_excluded(folder: FolderInfo, exclude: set[str]) -> bool:
    if folder.display_name in exclude:
        return True
    last_segment = folder.display_name.rsplit("/", 1)[-1]
    return last_segment in exclude


class Archiver:
    def __init__(
        self,
        config: Config,
        notifier: Notifier,
        state: StateStore,
        imap_client_factory: Callable[[], ImapClient] | None = None,
    ) -> None:
        self.config = config
        self.notifier = notifier
        self.state = state
        self._imap_client_factory = imap_client_factory or self._default_imap_client
        self._pending_errors: list[str] = []

    def _default_imap_client(self) -> ImapClient:
        return ImapClient(
            self.config.imap_host,
            self.config.imap_port,
            self.config.imap_user,
            self.config.imap_password,
        )

    def run(self) -> RunResult:
        started_at = datetime.now(UTC)
        result = RunResult(started_at=started_at, dry_run=self.config.dry_run)
        today = started_at.date()
        self._pending_errors = []
        lock = LockFile(self.config.lock_file)

        try:
            mount_result = check_mount(self.config.archive_root, self.config.mount_marker)
            if not mount_result.ok:
                self._handle_critical(result, "NAS-Mount fehlt", mount_result.reason)
                return result

            try:
                lock.acquire()
            except LockHeldError as exc:
                logger.info("skipping run: %s", exc)
                result.skipped = True
                return result
            except OSError as exc:
                self._handle_critical(result, "Lockfile konnte nicht angelegt werden", str(exc))
                return result

            self._run_locked(result)
            return result
        except Exception as exc:  # noqa: BLE001 - any unhandled failure must still send an error mail
            logger.exception("unexpected error during run")
            self._handle_critical(result, "Unerwarteter Fehler", f"{type(exc).__name__}: {exc}")
            return result
        finally:
            lock.release()
            result.finished_at = datetime.now(UTC)
            if not result.skipped:
                self._record_and_maybe_report(result, today)

    def _run_locked(self, result: RunResult) -> None:
        client = self._imap_client_factory()
        try:
            try:
                client.connect()
            except (ImapError, OSError) as exc:
                self._handle_critical(result, "IMAP-Login fehlgeschlagen", str(exc))
                return
            try:
                self._process(client, result)
            except AbortRun:
                pass
        finally:
            client.close()

    def _process(self, client: ImapClient, result: RunResult) -> None:
        try:
            folders = client.list_folders()
        except ImapError as exc:
            self._handle_critical(result, "IMAP-Fehler beim Auflisten der Ordner", str(exc))
            raise AbortRun from exc

        all_headers: list[MessageHeader] = []
        for folder in folders:
            try:
                all_headers.extend(client.message_headers(folder))
            except ImapError as exc:
                self._handle_critical(
                    result, f"IMAP-Fehler beim Lesen von Ordner {folder.display_name}", str(exc)
                )
                raise AbortRun from exc

        fill_bytes = sum(h.size for h in all_headers)
        result.fill_before = fill_bytes
        result.fill_after = fill_bytes
        quota = self.config.quota_bytes
        trigger = self.config.trigger_bytes
        target = self.config.target_bytes
        pct = (fill_bytes / quota * 100) if quota else 0.0

        logger.info(
            "current fill level: %s / %s (%.1f%%)",
            format_bytes(fill_bytes),
            format_bytes(quota),
            pct,
        )

        if fill_bytes < trigger:
            logger.info("below trigger threshold (%s), nothing to do", format_bytes(trigger))
            return

        result.action_taken = True
        logger.warning(
            "trigger threshold exceeded (%s >= %s), archiving oldest mail toward target %s",
            format_bytes(fill_bytes),
            format_bytes(trigger),
            format_bytes(target),
        )

        exclude = set(self.config.exclude_folders)
        candidates = [h for h in all_headers if not _is_excluded(h.folder, exclude)]
        candidates.sort(key=lambda h: h.date)

        for header in candidates:
            if fill_bytes <= target:
                break
            if header.size > self.config.max_message_size_bytes:
                logger.warning(
                    "large message folder=%s uid=%s size=%s exceeds max_message_size (%s); "
                    "archiving individually",
                    header.folder.display_name,
                    header.uid,
                    format_bytes(header.size),
                    format_bytes(self.config.max_message_size_bytes),
                )
            fill_bytes -= self._process_message(client, header, result)
            result.fill_after = fill_bytes

        if fill_bytes > target:
            msg = (
                f"Nach Verarbeitung aller nicht ausgeschlossenen Nachrichten wurde der Zielwert "
                f"nicht erreicht (aktuell {format_bytes(fill_bytes)}, Ziel {format_bytes(target)})."
            )
            logger.warning(msg)
            self._pending_errors.append(f"Zielwert nicht erreichbar: {msg}")
            self.notifier.send_error("Zielwert nicht erreichbar", error_mail_body(msg))

    def _process_message(self, client: ImapClient, header: MessageHeader, result: RunResult) -> int:
        if self.config.dry_run:
            logger.info(
                "[DRY-RUN] wuerde archivieren+loeschen: folder=%s uid=%s date=%s size=%s",
                header.folder.display_name,
                header.uid,
                header.date.isoformat(),
                format_bytes(header.size),
            )
            result.archived_count += 1
            result.archived_bytes += header.size
            return header.size

        try:
            raw = client.fetch_full_message(header.folder, header.uid)
        except ImapError as exc:
            self._handle_critical(
                result,
                "Nachricht konnte nicht abgerufen werden",
                str(exc),
                context={"folder": header.folder.display_name, "uid": header.uid},
            )
            raise AbortRun from exc

        path = build_archive_path(
            self.config.archive_root,
            header.folder.display_name,
            header.date,
            header.message_id,
            raw,
        )
        context = {"folder": header.folder.display_name, "uid": header.uid, "path": str(path)}

        try:
            existing = find_existing_archive(path, raw)
            if existing is not None and not existing.ok:
                self._handle_critical(
                    result,
                    "Verifikation fehlgeschlagen (Konflikt im Archiv)",
                    existing.reason,
                    context,
                )
                raise AbortRun

            if existing is None:
                write_eml_atomic(path, raw)
                verify = verify_written(path, raw)
                if not verify.ok:
                    self._handle_critical(
                        result, "Verifikation fehlgeschlagen", verify.reason, context
                    )
                    raise AbortRun
        except OSError as exc:
            self._handle_critical(result, "Schreiben ins Archiv fehlgeschlagen", str(exc), context)
            raise AbortRun from exc

        if existing is None:
            logger.info(
                "archived folder=%s uid=%s -> %s", header.folder.display_name, header.uid, path
            )
        else:
            logger.info(
                "already archived from a previous, interrupted run (idempotent) "
                "folder=%s uid=%s -> %s; deleting from server now",
                header.folder.display_name,
                header.uid,
                path,
            )

        try:
            client.delete_message(header.folder, header.uid)
        except ImapError as exc:
            self._handle_critical(
                result, "Loeschen auf dem Server fehlgeschlagen", str(exc), context
            )
            raise AbortRun from exc

        result.archived_count += 1
        result.archived_bytes += header.size
        return header.size

    def _handle_critical(
        self, result: RunResult, subject: str, reason: str, context: dict | None = None
    ) -> None:
        logger.error("%s: %s", subject, reason)
        result.aborted = True
        result.abort_reason = reason
        self._pending_errors.append(f"{subject}: {reason}")
        self.notifier.send_error(subject, error_mail_body(reason, context))

    def _record_and_maybe_report(self, result: RunResult, today: date) -> None:
        errors = list(self._pending_errors)
        self.state.record_run(today, result.archived_count, result.archived_bytes, errors)
        self._pending_errors = []

        pending = self.state.pending_monthly_report(today)
        if pending is not None:
            month_key, stats = pending
            if stats is not None and stats.had_activity():
                body = monthly_report_body(
                    month_key, stats, result.fill_after, self.config.quota_bytes
                )
                self.notifier.send_report(f"Monatsbericht {month_key}", body)
            self.state.mark_reported(month_key)

        logger.info(
            "run finished in %.1fs: archived=%d (%s) fill=%s/%s aborted=%s",
            result.duration_seconds,
            result.archived_count,
            format_bytes(result.archived_bytes),
            format_bytes(result.fill_after),
            format_bytes(self.config.quota_bytes),
            result.aborted,
        )
