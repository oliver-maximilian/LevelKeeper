# Architektur

## Wie es funktioniert

Jeder Lauf (siehe `levelkeeper/archiver.py`):

1. Prüft, ob das Archiv-Verzeichnis (NAS-Mount) tatsächlich verfügbar
   ist (Marker-Datei-Check). Wenn nicht: Abbruch, Fehler-Mail, nichts
   wird verändert.
2. Verhindert überlappende Läufe per Lockfile.
3. Loggt sich per IMAP (SSL) ein, listet alle Ordner, summiert
   `RFC822.SIZE` über **alle** Ordner (auch ausgeschlossene) →
   Füllstand.
4. Ist der Füllstand unter dem Trigger: Ende, nur Log-Eintrag.
5. Sonst: alle Nachrichten aus nicht ausgeschlossenen Ordnern werden
   nach Datum sortiert (älteste zuerst) und einzeln verarbeitet, bis
   der Zielwert unterschritten ist:
   - `FETCH RFC822` vollständig abrufen
   - als `.eml` ins Archiv schreiben (atomarer Write)
   - Schreibvorgang verifizieren (Dateigröße + SHA-256)
   - **erst danach** auf dem Server löschen (`STORE +FLAGS \Deleted`
     + `EXPUNGE`)
   - schlägt irgendein Schritt fehl: Lauf bricht sofort ab,
     Fehler-Mail, die betroffene (und alle weiteren) Nachrichten
     bleiben unangetastet auf dem Server.
6. Am 1. des Monats: Versand eines Monatsberichts, aber nur wenn im
   Vormonat tatsächlich etwas passiert ist (Archivierungen oder
   Fehler).

## Module

Alle Bausteine liegen unter `levelkeeper/`:

| Modul | Zweck |
|---|---|
| `config.py` | TOML + ENV Konfiguration, Size-/Prozent-Parsing, Validierung |
| `imap_client.py` | IMAP-Wrapper (Ordner, Header-Scan, Fetch, Delete), Modified-UTF-7 |
| `storage.py` | Archiv-Pfad/-Dateiname, atomarer Write, Checksummen-Verifikation, Idempotenz |
| `mount_check.py` | NAS-Mount-Check per Marker-Datei |
| `state.py` | Persistenter JSON-Zustand für den Monatsbericht |
| `notifier.py` / `report.py` | SMTP-Versand, Mailtexte |
| `lockfile.py` | Verhindert überlappende Läufe |
| `archiver.py` | Kernlogik/Orchestrierung des Laufs |
| `scheduler.py` / `__main__.py` | interner Intervall-Loop bzw. CLI-Einstieg |
