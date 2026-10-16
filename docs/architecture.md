# Architektur

## Ablauf eines Laufs

Siehe `levelkeeper/archiver.py`.

1. NAS-Mount per Marker-Datei prüfen. Fehlt er: Abbruch, Fehler-Mail, nichts wird verändert.
2. Lockfile setzen (verhindert überlappende Läufe).
3. Per IMAP (SSL) einloggen, alle Ordner listen und `RFC822.SIZE` über alle Ordner summieren (auch ausgeschlossene). Das ist der Füllstand.
4. Unter dem Trigger: Ende, nur ein Log-Eintrag.
5. Sonst alle Mails aus nicht ausgeschlossenen Ordnern nach Datum sortieren (älteste zuerst) und einzeln verarbeiten, bis der Zielwert unterschritten ist:
   - `FETCH RFC822`
   - als `.eml` atomar ins Archiv schreiben
   - Größe und SHA-256 verifizieren
   - erst danach auf dem Server löschen (`STORE +FLAGS \Deleted` und `UID EXPUNGE`)
   - Scheitert ein Schritt, bricht der Lauf sofort ab und schickt eine Fehler-Mail. Die betroffene und alle weiteren Mails bleiben auf dem Server.
6. Am 1. des Monats geht ein Monatsbericht raus, aber nur wenn im Vormonat etwas passiert ist (Archivierungen oder Fehler).

## Module

Alle unter `levelkeeper/`.

| Modul | Zweck |
|---|---|
| `config.py` | TOML + ENV, Size-/Prozent-Parsing, Validierung |
| `imap_client.py` | IMAP-Wrapper (Ordner, Header-Scan, Fetch, Delete), Modified-UTF-7, UIDVALIDITY-Prüfung |
| `storage.py` | Archiv-Pfad und Dateiname, atomarer Write, Checksummen-Verifikation, Idempotenz |
| `mount_check.py` | NAS-Mount-Check per Marker-Datei |
| `state.py` | JSON-Zustand für Monatsbericht und Fehler-Mail-Entprellung |
| `notifier.py` / `report.py` | SMTP-Versand, Mailtexte |
| `heartbeat.py` | optionaler Push nach erfolgreichem Lauf |
| `lockfile.py` | Lockfile gegen überlappende Läufe |
| `archiver.py` | Kernlogik des Laufs |
| `scheduler.py` / `__main__.py` | Intervall-Loop und CLI-Einstieg |
