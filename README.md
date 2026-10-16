# LevelKeeper

Keeps an IMAP mailbox below a fill level. Once the trigger is exceeded, LevelKeeper archives the oldest mails as `.eml` to the NAS and deletes them from the server only after the copy is verified.

One deployment manages one mailbox. For more mailboxes, run several instances (Compose projects) with their own configuration.

## Quick start

```
cp .env.example .env
docker compose run --rm levelkeeper --once --dry-run
docker compose up -d
```

Check the dry run and set up the NAS mount before the first real run. Details in [docs/setup.md](docs/setup.md).

## Documentation

- [docs/architecture.md](docs/architecture.md): run flow, modules
- [docs/setup.md](docs/setup.md): NAS mount, configuration, dry run, operation, multiple mailboxes
- [docs/operations.md](docs/operations.md): notifications, operational safety
- [GitHub Releases](https://github.com/oliver-maximilian/LevelKeeper/releases): changes per version (`git-cliff`, see `just changelog`)

## Non-goals

- No full-text search or index over the archive.
- No restore into the mailbox (restore = import the `.eml` manually in a mail client).
- No GoBD/compliance archiving, private tool only.

## Development

```
just init
just test
just test-integration   # real Dovecot in docker
```

More commands in the [justfile](justfile) (`run`, `format`, `lint`, `changelog`). No runtime dependencies: standard library only (`imaplib`, `email`, `smtplib`, `tomllib`), Python 3.11+.
