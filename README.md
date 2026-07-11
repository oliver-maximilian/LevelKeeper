# LevelKeeper

IMAP-Postfach-Füllstandsregelung: archiviert die ältesten E-Mails
eines Postfachs auf ein NAS und löscht sie erst nach verifizierter
Ablage vom Server, sobald ein konfigurierbarer Füllstand
überschritten wird.

Ein Deployment verwaltet **ein** Postfach. Für mehrere Postfächer
werden mehrere Instanzen (Compose-Projekte) mit je eigener
Konfiguration betrieben.

## Kurzstart

```
cp .env.example .env
docker compose run --rm levelkeeper --once --dry-run
docker compose up -d
```

Vor dem ersten echten Lauf unbedingt den Dry-Run prüfen und den
NAS-Mount einrichten - siehe [docs/setup.md](docs/setup.md) für die
vollständige Anleitung.

## Dokumentation

- [docs/architecture.md](docs/architecture.md) - Ablauf eines Laufs,
  Modulübersicht
- [docs/setup.md](docs/setup.md) - NAS-Mount, Konfiguration,
  Dry-Run, Betrieb, mehrere Postfächer
- [docs/operations.md](docs/operations.md) - Benachrichtigungen,
  Betriebssicherheit
- [CHANGELOG.md](CHANGELOG.md) - Änderungen je Release

## Nicht-Ziele

- Keine Volltextsuche/Index über das Archiv.
- Kein Zurückspielen archivierter Mails ins Postfach (Restore =
  manueller `.eml`-Import im Mail-Client).
- Keine GoBD-/Compliance-Archivierung - reines privates Werkzeug.

## Entwicklung

```
just init
just test
```

Siehe [justfile](justfile) für weitere Kommandos (`run`, `format`,
`lint`, `changelog`). Keine externen Laufzeit-Abhängigkeiten
(`imaplib`, `email`, `smtplib`, `tomllib` - alles
Standardbibliothek, Python 3.11+).
