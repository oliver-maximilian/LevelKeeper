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
- **Entprellung**: Dieselbe Fehler-Mail (gleicher Betreff und Grund)
  geht höchstens einmal pro 24 Stunden raus. Der Zeitpunkt liegt in
  der State-Datei und überlebt Neustarts. Der Fehler zählt trotzdem
  für den Monatsbericht.
- **Heartbeat** (optional, `heartbeat_url` bzw.
  `LEVELKEEPER_HEARTBEAT_URL`): Nach jedem erfolgreichen Lauf wird die
  URL per GET aufgerufen, z. B. ein Uptime-Kuma-Push-Monitor. Bei
  abgebrochenen oder übersprungenen Läufen bleibt der Ping aus. So
  fällt auch ein hängender oder gestoppter Container auf. Ein
  fehlschlagender Ping wird nur geloggt.

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
- **UIDVALIDITY**: Der Scan merkt sich je Ordner die UIDVALIDITY.
  Vor Abruf und Löschen wird sie erneut geprüft. Hat der Server den
  Ordner neu aufgebaut, bricht der Lauf mit Fehler-Mail ab, statt
  per veralteter UID eine falsche Mail zu löschen.
- **Gezieltes Löschen**: Gelöscht wird per `UID EXPUNGE` (Erweiterung
  UIDPLUS). Nur die archivierte Mail verschwindet, andere im Mail-Client
  als gelöscht markierte Mails bleiben unberührt. Meldet der Server
  UIDPLUS nicht, löscht LevelKeeper nichts und meldet einen Fehler.
