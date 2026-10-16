# Setup

## 1. Mount the NAS share on the host

LevelKeeper does not mount anything itself. The host does (SMB or NFS), e.g. via `/etc/fstab` or a systemd `.mount` unit. Example `fstab` for SMB:

```
//nas.local/mailarchiv /mnt/nas/mail-archive cifs credentials=/root/.smb-cred,uid=1000,gid=1000,iocharset=utf8,vers=3.0 0 0
```

`uid=1000,gid=1000` lets the container user (`levelkeeper`, UID 1000) write to the share.

Then create the marker file once. The mount check looks for it before every run and prevents writing to the local container disk when the mount is missing:

```
touch /mnt/nas/mail-archive/.levelkeeper_mounted
```

## 2. Configuration

```
cp .env.example .env
cp config/config.example.toml config/config.toml   # optional, ENV alone works too
```

ENV variables (`LEVELKEEPER_*`, see `.env.example`) take precedence over `config.toml`. Credentials do not belong in the image or repo (`config.toml` and `.env` are in `.gitignore`).

Key values:

- `quota`, `trigger`, `target`: absolute (`"1.5GB"`) or percent (`"80%"`, relative to `quota`). `target` must be below `trigger`, otherwise startup aborts with an error message.
- Sizes are binary (`1 GB == 1024**3 bytes`).
- `exclude_folders`: folders that are never archived (but count toward the fill level), e.g. `Trash,Junk,Drafts`.
- `run_interval`: e.g. `1h`. Leave empty if host cron calls `docker compose run` (see below).
- `heartbeat_url`: optional push after every successful run (Uptime Kuma).

## 3. Data directory

`/data` holds the lockfile and the state for the monthly report and error mail dedup. It must survive restarts.

```
mkdir -p data
chown -R 1000:1000 data   # container runs as UID 1000
```

## 4. First test: dry run

**Mandatory before the first real run.** Shows what would be archived and deleted, without writing:

```
docker compose run --rm levelkeeper --once --dry-run
```

Check the log (fill level, planned actions), then set `DRY_RUN=false`. The dry run deletes nothing and therefore does not check whether the server supports `UIDPLUS`. If it does not, deleting fails in the first real run with an error mail.

## 5. Operation

Two options (see `docker-compose.yml`):

- **Internal scheduler:** set `run_interval`, the container runs permanently.
  ```
  docker compose up -d
  ```
- **Host cron:** leave `run_interval` empty, a cron job calls a single run.
  ```
  0 * * * * cd /path/to/levelkeeper && docker compose run --rm levelkeeper --once
  ```

## Multiple mailboxes

One deployment = one mailbox. For a second one, copy the project directory (at least `docker-compose.yml` and `.env`) and start it there as usual:

```
cp -r levelkeeper levelkeeper-family
cd levelkeeper-family
cp .env.example .env   # own credentials, own NAS_ARCHIVE_PATH/DATA_PATH
docker compose up -d
```

Each directory has its own `.env`, a `--env-file` flag is never needed.

**Do not** share one directory with several `.env.<name>` files and switch with `docker compose --env-file .env.<name> up -d`. The flag only fills the `${...}` placeholders in `docker-compose.yml` (e.g. `NAS_ARCHIVE_PATH`). Which file the service loads via `env_file:` stays fixed at `.env`. Best case, `up -d` aborts with `required variable NAS_ARCHIVE_PATH is missing a value`, worst case the wrong credentials are silently loaded.
