# LevelKeeper

IMAP-Postfach-Füllstandsregelung: archiviert die ältesten E-Mails eines
Postfachs auf ein NAS und löscht sie erst nach verifizierter Ablage vom
Server, sobald ein konfigurierbarer Füllstand überschritten wird.

Ein Deployment verwaltet **ein** Postfach. Für mehrere Postfächer werden
mehrere Instanzen (Compose-Projekte) mit je eigener Konfiguration betrieben.

## Wie es funktioniert

Jeder Lauf (siehe `levelkeeper/archiver.py`):

1. Prüft, ob das Archiv-Verzeichnis (NAS-Mount) tatsächlich verfügbar ist
   (Marker-Datei-Check). Wenn nicht: Abbruch, Fehler-Mail, nichts wird
   verändert.
2. Verhindert überlappende Läufe per Lockfile.
3. Loggt sich per IMAP (SSL) ein, listet alle Ordner, summiert
   `RFC822.SIZE` über **alle** Ordner (auch ausgeschlossene) → Füllstand.
4. Ist der Füllstand unter dem Trigger: Ende, nur Log-Eintrag.
5. Sonst: alle Nachrichten aus nicht ausgeschlossenen Ordnern werden nach
   Datum sortiert (älteste zuerst) und einzeln verarbeitet, bis der
   Zielwert unterschritten ist:
   - `FETCH RFC822` vollständig abrufen
   - als `.eml` ins Archiv schreiben (atomarer Write)
   - Schreibvorgang verifizieren (Dateigröße + SHA-256)
   - **erst danach** auf dem Server löschen (`STORE +FLAGS \Deleted` +
     `EXPUNGE`)
   - schlägt irgendein Schritt fehl: Lauf bricht sofort ab, Fehler-Mail,
     die betroffene (und alle weiteren) Nachrichten bleiben unangetastet
     auf dem Server.
6. Am 1. des Monats: Versand eines Monatsberichts, aber nur wenn im
   Vormonat tatsächlich etwas passiert ist (Archivierungen oder Fehler).

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

## Setup

### 1. NAS-Share auf dem Host mounten

LevelKeeper mountet nichts selbst - das ist Aufgabe des Hosts (SMB oder
NFS), z. B. per `/etc/fstab` oder systemd `.mount`-Unit. Beispiel `fstab`
für SMB:

```
//nas.local/mailarchiv /mnt/nas/mail-archive cifs credentials=/root/.smb-cred,uid=1000,gid=1000,iocharset=utf8,vers=3.0 0 0
```

`uid=1000,gid=1000` sorgt dafür, dass der Container-User (`levelkeeper`,
UID 1000) auf dem Share schreiben darf.

Danach einmalig die Marker-Datei anlegen, die der Mount-Check vor jedem
Lauf prüft (verhindert, dass bei einem fehlenden Mount versehentlich auf
die lokale Containerplatte geschrieben wird):

```
touch /mnt/nas/mail-archive/.levelkeeper_mounted
```

### 2. Konfiguration

```
cp .env.example .env
cp config/config.example.toml config/config.toml   # optional, ENV reicht auch
```

ENV-Variablen (`LEVELKEEPER_*`, siehe `.env.example`) haben Vorrang vor
`config.toml`. Zugangsdaten gehören nicht ins Image oder ins Repo -
`config.toml` und `.env` sind in `.gitignore`.

Wichtige Werte:

- `quota` / `trigger` / `target`: absolut (`"1.5GB"`) oder prozentual
  (`"80%"`, bezogen auf `quota`). `target` muss unter `trigger` liegen,
  sonst bricht der Start mit einer klaren Fehlermeldung ab.
- Größen werden binär interpretiert (`1 GB == 1024**3 Byte`).
- `exclude_folders`: Ordner, die nie archiviert/geleert werden (zählen
  aber weiter zum Füllstand), z. B. `Trash,Junk,Drafts`.
- `run_interval`: z. B. `1h`. Leer lassen, wenn stattdessen Host-Cron
  `docker compose run` aufruft (siehe unten).

### 3. Datenverzeichnis

`/data` enthält Lockfile und den persistenten Zustand für den
Monatsbericht - muss Neustarts überleben.

```
mkdir -p data
chown -R 1000:1000 data   # Container läuft als UID 1000
```

### 4. Erster Test: Dry-Run

**Pflicht vor dem ersten echten Lauf.** Zeigt, was archiviert/gelöscht
würde, ohne zu schreiben oder zu löschen:

```
docker compose run --rm levelkeeper --once --dry-run
```

Log-Ausgabe prüfen (Füllstand, geplante Aktionen), dann `DRY_RUN=false`
setzen.

### 5. Betrieb

Zwei gleichwertige Optionen (siehe `docker-compose.yml`):

- **Interner Scheduler:** `run_interval` gesetzt, Container läuft dauerhaft:
  ```
  docker compose up -d
  ```
- **Host-Cron:** `run_interval` leer lassen, Cronjob auf dem Host ruft
  einen Einzellauf auf:
  ```
  0 * * * * cd /pfad/zu/levelkeeper && docker compose run --rm levelkeeper --once
  ```

### Mehrere Postfächer

Ein Deployment = ein Postfach. Für ein zweites Postfach dasselbe
`docker-compose.yml` mit eigenem Projektnamen und eigener `.env` erneut
starten, jeweils mit eigenem `NAS_ARCHIVE_PATH`/`DATA_PATH`/`CONFIG_PATH`:

```
docker compose -p levelkeeper-oliver  --env-file .env.oliver  up -d
docker compose -p levelkeeper-familie --env-file .env.familie up -d
```

## Benachrichtigungen

Versand per SMTP über `smtp.strato.de` (SSL/TLS), mit denselben
Zugangsdaten wie das überwachte Postfach.

- **Monatsbericht** am 1. des Monats, nur wenn im Vormonat etwas passiert
  ist: Anzahl archivierter Mails, freigegebener Speicher, aktueller
  Füllstand (absolut + %), aufgetretene Fehler.
- **Sofortige Fehler-Mail** bei: fehlendem NAS-Mount, IMAP-Login-Fehler,
  gescheiterter Verifikation, nicht erreichbarem Zielwert. Schlägt der
  Mailversand selbst fehl (z. B. SMTP nicht erreichbar), wird das nur
  geloggt - der Lauf bricht deswegen nicht zusätzlich ab.

## Betriebssicherheit

- **Dry-Run** (`dry_run`/`--dry-run`): schreibt/löscht nichts, loggt nur.
- **Lockfile**: verhindert überlappende Läufe; erkennt und räumt Locks
  toter Prozesse automatisch auf.
- **Logging**: strukturiert nach stdout (`log_format = "text"` oder
  `"json"`), jeder Lauf loggt Füllstand, Aktionen, Dauer, Ergebnis.
- **Idempotenz**: Dateiname im Archiv ist deterministisch aus
  Message-ID (bzw. Nachrichteninhalt als Fallback) abgeleitet. Bricht ein
  Lauf zwischen Schreiben und Löschen ab, erkennt der nächste Lauf die
  bereits vorhandene, per Checksumme verifizierte Datei und überspringt
  den erneuten Schreibvorgang - es entstehen keine Duplikate.
- **Große Mails**: Nachrichten über `max_message_size` werden einzeln mit
  einer eigenen Log-Zeile markiert, blockieren den Lauf aber nicht.

## Nicht-Ziele

- Keine Volltextsuche/Index über das Archiv.
- Kein Zurückspielen archivierter Mails ins Postfach (Restore = manueller
  `.eml`-Import im Mail-Client).
- Keine GoBD-/Compliance-Archivierung - reines privates Werkzeug.

## Entwicklung

```
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Keine externen Laufzeit-Abhängigkeiten (`imaplib`, `email`, `smtplib`,
`tomllib` - alles Standardbibliothek, Python 3.11+).
