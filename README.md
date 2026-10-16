# LevelKeeper

Hält ein IMAP-Postfach unter einem Füllstand. Wird der Trigger überschritten, archiviert LevelKeeper die ältesten Mails als `.eml` aufs NAS und löscht sie erst nach verifizierter Ablage vom Server.

Ein Deployment verwaltet ein Postfach. Für mehrere Postfächer laufen mehrere Instanzen (Compose-Projekte) mit eigener Konfiguration.

## Kurzstart

```
cp .env.example .env
docker compose run --rm levelkeeper --once --dry-run
docker compose up -d
```

Vor dem ersten echten Lauf den Dry-Run prüfen und den NAS-Mount einrichten. Details in [docs/setup.md](docs/setup.md).

## Dokumentation

- [docs/architecture.md](docs/architecture.md): Ablauf eines Laufs, Module
- [docs/setup.md](docs/setup.md): NAS-Mount, Konfiguration, Dry-Run, Betrieb, mehrere Postfächer
- [docs/operations.md](docs/operations.md): Benachrichtigungen, Betriebssicherheit
- [GitHub Releases](https://github.com/oliver-maximilian/LevelKeeper/releases): Änderungen je Version (`git-cliff`, siehe `just changelog`)

## Nicht-Ziele

- Keine Volltextsuche oder Index über das Archiv.
- Kein Zurückspielen ins Postfach (Restore = `.eml` manuell im Mail-Client importieren).
- Keine GoBD-/Compliance-Archivierung, nur privates Werkzeug.

## Entwicklung

```
just init
just test
```

Weitere Kommandos im [justfile](justfile) (`run`, `format`, `lint`, `changelog`). Keine Laufzeit-Abhängigkeiten: nur Standardbibliothek (`imaplib`, `email`, `smtplib`, `tomllib`), Python 3.11+.
