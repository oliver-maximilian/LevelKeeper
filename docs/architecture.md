# Architecture

## Run flow

See `levelkeeper/archiver.py`.

1. Check the NAS mount via marker file. If missing: abort, error mail, nothing changes.
2. Take the lockfile (prevents overlapping runs).
3. Log in via IMAP (SSL), list all folders and sum `RFC822.SIZE` over all folders (excluded ones too). That is the fill level.
4. Below the trigger: done, log entry only.
5. Otherwise sort all mails from non-excluded folders by date (oldest first) and process them one by one until the target is reached:
   - `FETCH RFC822`
   - write the `.eml` atomically to the archive
   - verify size and SHA-256
   - only then delete on the server (`STORE +FLAGS \Deleted` and `UID EXPUNGE`)
   - If a step fails, the run aborts immediately and sends an error mail. The affected and all remaining mails stay on the server.
6. On the 1st of the month a monthly report goes out, but only if something happened in the previous month (archivals or errors).

## Modules

All under `levelkeeper/`.

| Module | Purpose |
|---|---|
| `config.py` | TOML + ENV, size/percent parsing, validation |
| `imap_client.py` | IMAP wrapper (folders, header scan, fetch, delete), modified UTF-7, UIDVALIDITY check |
| `storage.py` | archive path and filename, atomic write, checksum verification, idempotency |
| `mount_check.py` | NAS mount check via marker file |
| `state.py` | JSON state for the monthly report and error mail dedup |
| `notifier.py` / `report.py` | SMTP sending, mail bodies |
| `heartbeat.py` | optional push after a successful run |
| `lockfile.py` | lockfile against overlapping runs |
| `archiver.py` | core run logic |
| `scheduler.py` / `__main__.py` | interval loop and CLI entry |
