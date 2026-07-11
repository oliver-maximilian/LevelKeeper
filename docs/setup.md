# Setup

## 1. NAS-Share auf dem Host mounten

LevelKeeper mountet nichts selbst - das ist Aufgabe des Hosts (SMB
oder NFS), z. B. per `/etc/fstab` oder systemd `.mount`-Unit.
Beispiel `fstab` für SMB:

```
//nas.local/mailarchiv /mnt/nas/mail-archive cifs credentials=/root/.smb-cred,uid=1000,gid=1000,iocharset=utf8,vers=3.0 0 0
```

`uid=1000,gid=1000` sorgt dafür, dass der Container-User
(`levelkeeper`, UID 1000) auf dem Share schreiben darf.

Danach einmalig die Marker-Datei anlegen, die der Mount-Check vor
jedem Lauf prüft (verhindert, dass bei einem fehlenden Mount
versehentlich auf die lokale Containerplatte geschrieben wird):

```
touch /mnt/nas/mail-archive/.levelkeeper_mounted
```

## 2. Konfiguration

```
cp .env.example .env
cp config/config.example.toml config/config.toml   # optional, ENV reicht auch
```

ENV-Variablen (`LEVELKEEPER_*`, siehe `.env.example`) haben Vorrang
vor `config.toml`. Zugangsdaten gehören nicht ins Image oder ins
Repo - `config.toml` und `.env` sind in `.gitignore`.

Wichtige Werte:

- `quota` / `trigger` / `target`: absolut (`"1.5GB"`) oder
  prozentual (`"80%"`, bezogen auf `quota`). `target` muss unter
  `trigger` liegen, sonst bricht der Start mit einer klaren
  Fehlermeldung ab.
- Größen werden binär interpretiert (`1 GB == 1024**3 Byte`).
- `exclude_folders`: Ordner, die nie archiviert/geleert werden
  (zählen aber weiter zum Füllstand), z. B. `Trash,Junk,Drafts`.
- `run_interval`: z. B. `1h`. Leer lassen, wenn stattdessen
  Host-Cron `docker compose run` aufruft (siehe unten).

## 3. Datenverzeichnis

`/data` enthält Lockfile und den persistenten Zustand für den
Monatsbericht - muss Neustarts überleben.

```
mkdir -p data
chown -R 1000:1000 data   # Container läuft als UID 1000
```

## 4. Erster Test: Dry-Run

**Pflicht vor dem ersten echten Lauf.** Zeigt, was
archiviert/gelöscht würde, ohne zu schreiben oder zu löschen:

```
docker compose run --rm levelkeeper --once --dry-run
```

Log-Ausgabe prüfen (Füllstand, geplante Aktionen), dann
`DRY_RUN=false` setzen.

## 5. Betrieb

Zwei gleichwertige Optionen (siehe `docker-compose.yml`):

- **Interner Scheduler:** `run_interval` gesetzt, Container läuft
  dauerhaft:
  ```
  docker compose up -d
  ```
- **Host-Cron:** `run_interval` leer lassen, Cronjob auf dem Host
  ruft einen Einzellauf auf:
  ```
  0 * * * * cd /pfad/zu/levelkeeper && docker compose run --rm levelkeeper --once
  ```

## Mehrere Postfächer

Ein Deployment = ein Postfach. Für ein zweites Postfach dasselbe
`docker-compose.yml` mit eigenem Projektnamen und eigener `.env`
erneut starten, jeweils mit eigenem
`NAS_ARCHIVE_PATH`/`DATA_PATH`/`CONFIG_PATH`:

```
docker compose -p levelkeeper-oliver  --env-file .env.oliver  up -d
docker compose -p levelkeeper-familie --env-file .env.familie up -d
```
