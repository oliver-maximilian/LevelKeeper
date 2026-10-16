# Setup

## 1. NAS-Share auf dem Host mounten

LevelKeeper mountet nichts selbst. Das macht der Host (SMB oder NFS), z. B. per `/etc/fstab` oder systemd `.mount`-Unit. Beispiel `fstab` für SMB:

```
//nas.local/mailarchiv /mnt/nas/mail-archive cifs credentials=/root/.smb-cred,uid=1000,gid=1000,iocharset=utf8,vers=3.0 0 0
```

`uid=1000,gid=1000` erlaubt dem Container-User (`levelkeeper`, UID 1000) das Schreiben auf dem Share.

Danach einmalig die Marker-Datei anlegen. Der Mount-Check prüft sie vor jedem Lauf und verhindert, dass bei fehlendem Mount auf die lokale Containerplatte geschrieben wird:

```
touch /mnt/nas/mail-archive/.levelkeeper_mounted
```

## 2. Konfiguration

```
cp .env.example .env
cp config/config.example.toml config/config.toml   # optional, ENV reicht auch
```

ENV-Variablen (`LEVELKEEPER_*`, siehe `.env.example`) haben Vorrang vor `config.toml`. Zugangsdaten gehören nicht ins Image oder Repo (`config.toml` und `.env` stehen in `.gitignore`).

Wichtige Werte:

- `quota`, `trigger`, `target`: absolut (`"1.5GB"`) oder prozentual (`"80%"`, bezogen auf `quota`). `target` muss unter `trigger` liegen, sonst bricht der Start mit Fehlermeldung ab.
- Größen sind binär (`1 GB == 1024**3 Byte`).
- `exclude_folders`: Ordner, die nie archiviert werden (zählen aber zum Füllstand), z. B. `Trash,Junk,Drafts`.
- `run_interval`: z. B. `1h`. Leer lassen, wenn Host-Cron `docker compose run` aufruft (siehe unten).
- `heartbeat_url`: optionaler Push nach jedem erfolgreichen Lauf (Uptime Kuma).

## 3. Datenverzeichnis

`/data` enthält Lockfile und Zustand für Monatsbericht und Fehler-Mail-Entprellung. Es muss Neustarts überleben.

```
mkdir -p data
chown -R 1000:1000 data   # Container läuft als UID 1000
```

## 4. Erster Test: Dry-Run

**Pflicht vor dem ersten echten Lauf.** Zeigt, was archiviert und gelöscht würde, ohne zu schreiben:

```
docker compose run --rm levelkeeper --once --dry-run
```

Log prüfen (Füllstand, geplante Aktionen), dann `DRY_RUN=false` setzen. Der Dry-Run löscht nichts und prüft deshalb nicht, ob der Server `UIDPLUS` kann. Fehlt es, scheitert das Löschen im ersten echten Lauf mit Fehler-Mail.

## 5. Betrieb

Zwei Optionen (siehe `docker-compose.yml`):

- **Interner Scheduler:** `run_interval` setzen, Container läuft dauerhaft.
  ```
  docker compose up -d
  ```
- **Host-Cron:** `run_interval` leer lassen, Cronjob ruft einen Einzellauf auf.
  ```
  0 * * * * cd /pfad/zu/levelkeeper && docker compose run --rm levelkeeper --once
  ```

## Mehrere Postfächer

Ein Deployment = ein Postfach. Für ein zweites das Projektverzeichnis kopieren (mindestens `docker-compose.yml` und `.env`) und dort normal starten:

```
cp -r levelkeeper levelkeeper-familie
cd levelkeeper-familie
cp .env.example .env   # eigene Zugangsdaten, eigener NAS_ARCHIVE_PATH/DATA_PATH
docker compose up -d
```

Jedes Verzeichnis hat seine eigene `.env`, ein `--env-file`-Flag ist nie nötig.

**Nicht** ein Verzeichnis mit mehreren `.env.<name>` teilen und per `docker compose --env-file .env.<name> up -d` umschalten. Das Flag füllt nur die `${...}`-Platzhalter in `docker-compose.yml` (z. B. `NAS_ARCHIVE_PATH`). Welche Datei der Service per `env_file:` lädt, bleibt fest `.env`. Im besten Fall bricht `up -d` mit `required variable NAS_ARCHIVE_PATH is missing a value` ab, im schlechtesten werden still die falschen Zugangsdaten geladen.
