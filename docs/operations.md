# Betrieb

## Benachrichtigungen

Versand per SMTP über `smtp.strato.de` (SSL/TLS), mit denselben
Zugangsdaten wie das überwachte Postfach.

- **Monatsbericht** am 1. des Monats, nur wenn im Vormonat etwas
  passiert ist: Anzahl archivierter Mails, freigegebener Speicher,
  aktueller Füllstand (absolut + %), aufgetretene Fehler.
- **Sofortige Fehler-Mail** bei: fehlendem NAS-Mount,
  IMAP-Login-Fehler, gescheiterter Verifikation, nicht erreichbarem
  Zielwert. Schlägt der Mailversand selbst fehl (z. B. SMTP nicht
  erreichbar), wird das nur geloggt - der Lauf bricht deswegen nicht
  zusätzlich ab.

## Betriebssicherheit

- **Dry-Run** (`dry_run`/`--dry-run`): schreibt/löscht nichts,
  loggt nur.
- **Lockfile**: verhindert überlappende Läufe; erkennt und räumt
  Locks toter Prozesse automatisch auf.
- **Logging**: strukturiert nach stdout (`log_format = "text"` oder
  `"json"`), jeder Lauf loggt Füllstand, Aktionen, Dauer, Ergebnis.
- **Idempotenz**: Dateiname im Archiv ist deterministisch aus
  Message-ID (bzw. Nachrichteninhalt als Fallback) abgeleitet.
  Bricht ein Lauf zwischen Schreiben und Löschen ab, erkennt der
  nächste Lauf die bereits vorhandene, per Checksumme verifizierte
  Datei und überspringt den erneuten Schreibvorgang - es entstehen
  keine Duplikate.
- **Große Mails**: Nachrichten über `max_message_size` werden
  einzeln mit einer eigenen Log-Zeile markiert, blockieren den Lauf
  aber nicht.
