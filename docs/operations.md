# Operations

## Notifications

Sent via SMTP over `smtp.strato.de` (SSL/TLS) with the same credentials as the mailbox.

- **Monthly report** on the 1st, only if something happened in the previous month: archived mails, freed storage, fill level (absolute and %), errors.
- **Immediate error mail** on missing NAS mount, IMAP login failure, failed verification, changed UIDVALIDITY and unreachable target. If sending the mail itself fails, it is only logged.
- **Dedup:** the same error mail (same subject and reason) goes out at most once per 24 hours. The timestamp lives in the state file and survives restarts. The error still counts for the monthly report.
- **Heartbeat** (optional, `heartbeat_url` or `LEVELKEEPER_HEARTBEAT_URL`): after every successful run LevelKeeper sends a GET to the URL, e.g. an Uptime Kuma push monitor. Aborted or skipped runs send no ping, so a hung or stopped container shows up too. A failed ping is only logged.

## Operational safety

- **Healthcheck:** the image checks every 5 minutes (`--healthcheck`) that the last successful run is younger than 3 intervals. Without `run_interval` (host cron) it always passes. `docker ps` shows `unhealthy` for a stuck or constantly failing container, and aborted runs do not count as success.
- **Dry run** (`dry_run` / `--dry-run`): writes and deletes nothing, only logs.
- **Lockfile:** prevents overlapping runs and cleans up locks of dead processes itself.
- **Logging:** to stdout, `log_format = "json"` (default in the examples, for Loki) or `"text"`. Every run logs fill level, actions, duration and result.
- **Idempotency:** the archive filename is derived deterministically from the Message-ID (fallback: content). If a run aborts between write and delete, the next run recognizes the verified file and skips the write. No duplicates.
- **Large mails:** mails above `max_message_size` get their own log line and do not block the run.
- **UIDVALIDITY:** the scan remembers it per folder and checks it again before fetch and delete. If the server rebuilt the folder, the run aborts with an error mail instead of deleting a wrong mail via a stale UID.
- **Targeted delete:** via `UID EXPUNGE` (UIDPLUS). Only the archived mail disappears, mails flagged as deleted in the mail client stay untouched. If the server lacks UIDPLUS, LevelKeeper deletes nothing and reports an error.
