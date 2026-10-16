# Betrieb

## Benachrichtigungen

Versand per SMTP über `smtp.strato.de` (SSL/TLS) mit denselben Zugangsdaten wie das Postfach.

- **Monatsbericht** am 1. des Monats, nur wenn im Vormonat etwas passiert ist: archivierte Mails, freigegebener Speicher, Füllstand (absolut und %), Fehler.
- **Sofortige Fehler-Mail** bei fehlendem NAS-Mount, IMAP-Login-Fehler, gescheiterter Verifikation, geänderter UIDVALIDITY und nicht erreichbarem Zielwert. Schlägt der Mailversand selbst fehl, wird das nur geloggt.
- **Entprellung:** Dieselbe Fehler-Mail (gleicher Betreff und Grund) geht höchstens einmal pro 24 Stunden raus. Der Zeitpunkt liegt in der State-Datei und überlebt Neustarts. Der Fehler zählt trotzdem für den Monatsbericht.
- **Heartbeat** (optional, `heartbeat_url` oder `LEVELKEEPER_HEARTBEAT_URL`): Nach jedem erfolgreichen Lauf ruft LevelKeeper die URL per GET auf, z. B. einen Uptime-Kuma-Push-Monitor. Bei abgebrochenen oder übersprungenen Läufen bleibt der Ping aus, so fällt auch ein hängender Container auf. Ein fehlgeschlagener Ping wird nur geloggt.

## Betriebssicherheit

- **Dry-Run** (`dry_run` / `--dry-run`): schreibt und löscht nichts, loggt nur.
- **Lockfile:** verhindert überlappende Läufe und räumt Locks toter Prozesse selbst auf.
- **Logging:** nach stdout, `log_format = "text"` oder `"json"`. Jeder Lauf loggt Füllstand, Aktionen, Dauer und Ergebnis.
- **Idempotenz:** Der Dateiname im Archiv leitet sich deterministisch aus der Message-ID ab (Fallback: Inhalt). Bricht ein Lauf zwischen Schreiben und Löschen ab, erkennt der nächste die verifizierte Datei und überspringt das Schreiben. Es entstehen keine Duplikate.
- **Große Mails:** Mails über `max_message_size` bekommen eine eigene Log-Zeile und blockieren den Lauf nicht.
- **UIDVALIDITY:** Der Scan merkt sich sie je Ordner und prüft sie vor Abruf und Löschen erneut. Hat der Server den Ordner neu aufgebaut, bricht der Lauf mit Fehler-Mail ab, statt per alter UID eine falsche Mail zu löschen.
- **Gezieltes Löschen:** per `UID EXPUNGE` (UIDPLUS). Nur die archivierte Mail verschwindet, im Mail-Client als gelöscht markierte Mails bleiben unberührt. Meldet der Server kein UIDPLUS, löscht LevelKeeper nichts und meldet einen Fehler.
