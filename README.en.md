# zspace-emby-bridge

<img src="app/assets/icon-256.png" width="88" height="88" alt="zspace-emby-bridge icon">

**Two-way playback progress sync between Hills (any Emby client) and ZSpace's 极影视.**

极影视's Emby-compatible layer can read progress but never persists it: `Sessions/Playing*` always returns 400, `UserData` write endpoints are 404. This proxy sits in between, writes the position straight into 极影视's own SQLite database, and aligns read responses — so both sides agree, resume works, and deletions in 极影视 propagate.

[中文说明](README.md) · [Docker Hub](https://hub.docker.com/r/snarl6818/zspace-emby-bridge) · [Issues](https://github.com/Landslide3154/zspace-emby-bridge/issues)

## Features

- **Progress sync both ways**: movies, TV, anime, documentaries, plus custom categories
- **极影视 is authoritative**: its record wins; if it is cleared, the local copy is cleared too
- **Played sync**: marks watched past a threshold; per-episode for series, never whole-season by accident
- **Audio / subtitle preference**: writes the client's selection back to 极影视
- **Web console**: first visit asks for a password; change upstream URL, threshold, intervals, switches, log level and IP allowlist on the fly
- **Readable**: sync rows show title and file name; search by title, file name or collection_id
- **Diagnosable**: one-click upstream test, override/cleared events, currently playing items
- **Zero-copy media**: Range / HEAD / 206 pass through untouched
- **Redaction**: no tokens, Authorization or api_key in logs

## Architecture

```
Hills ──▶ bridge :8022 ──▶ 极影视 Emby :8021   read APIs / images / video streams forwarded as-is
                   └────▶ zvideo.db             progress, played flag, stream prefs
```

Sync rule: if 极影视 has a record, it wins. If it is explicitly empty and the local record is older than the grace window (15 s by default), the local record is considered deleted and removed.

## Quick start

Requires `/zspace/zsrp/sqlite/zvideo/zvideo.db` on the host (created by 极影视). The container must run as root to write it — Docker's default.

### Layout

`.env` must sit in the **same directory** as `docker-compose.yml` (`env_file` and the `${...}` interpolation both resolve against the compose file's directory):

```
<project dir>/
├── docker-compose.yml
├── .env                ← next to the compose file, name must be .env
└── config/             ← created on first start: console password, progress DB
```

On ZSpace, Docker-created projects live under
`/tmp/zfsv3/nvme12/<account>/data/docker/<project>/` (same place as jackett and komga).

> **The ZSpace Docker GUI rejects some bind mounts**: it validates `host:container` entries itself, so system
> partitions like `/zspace/...` are refused with
> `custom validation failed: invalid volume path: /zspace/zsrp/sqlite/zvideo`.
> The compose file is not wrong — the same config passes `docker compose config`; this is GUI-only validation.
>
> **To keep managing it in the GUI and still mount `/zspace`, use a named volume with the bind driver**: the GUI
> only sees a volume name, while the mount still lands on `/zspace`:
>
> ```yaml
> services:
>   bridge:
>     # ...rest unchanged...
>     volumes:
>       - ./config:/data
>       - zvideo-db:/zvideo          # a volume name, not a host path
>
> volumes:
>   zvideo-db:
>     driver: local
>     driver_opts:
>       type: none
>       o: bind
>       device: /zspace/zsrp/sqlite/zvideo
> ```
>
> If the GUI also inspects the path inside `device:`, switch to an **external volume** — the path then appears
> only in a one-off creation step, and compose references just the name:
>
> ```bash
> sudo docker volume create zvideo-db --driver local \
>   --opt type=none --opt o=bind --opt device=/zspace/zsrp/sqlite/zvideo
> ```
>
> ```yaml
>     volumes:
>       - ./config:/data
>       - zvideo-db:/zvideo
>
> volumes:
>   zvideo-db:
>     external: true
> ```
>
> Both variants are verified on a real ZSpace NAS: inside the container `ls /zvideo` shows `zvideo.db` (206 MB)
> and `zvideo.db-wal`, and `/healthz` returns 200.

### 1. `docker-compose.yml` (annotated, copy as-is)

```yaml
services:
  bridge:
    # keep this if Docker Hub is reachable; otherwise use docker.1ms.run/snarl6818/zspace-emby-bridge:latest
    image: snarl6818/zspace-emby-bridge:latest
    container_name: zspace-emby-bridge
    restart: unless-stopped
    ports:
      # all three values come from .env. Leaving BIND_IP empty binds 0.0.0.0,
      # which collides with whatever already owns 127.0.0.1:8022
      - "${BIND_IP:-0.0.0.0}:${BRIDGE_PORT:-8022}:${LISTEN_PORT:-8022}"
    env_file:
      - .env                                  # variables and account live here
    environment:
      NATIVE_MODE: local                      # write 极影视's DB from inside the container
      NATIVE_DB_PATH: /zvideo/zvideo.db       # in-container path, matches the mount below
      DB_PATH: /data/progress.db              # local progress DB, kept in ./config
    volumes:
      - ./config:/data                        # settings + progress DB next to the compose file
      # NATIVE_DB_DIR already defaults to the 极影视 directory, usually leave it
      - ${NATIVE_DB_DIR:-/zspace/zsrp/sqlite/zvideo}:/zvideo
```

### 2. `.env` (annotated, only three values are required)

```ini
# ===== three required values =====

# [required 1] 极影视 Emby endpoint
UPSTREAM_URL=http://192.168.2.8:8021

# [required 2] ZSpace account (the user_name inside zvideo.db)
NATIVE_USER=

# [required 3] bind address: on ZSpace use the NAS LAN IP
# (0.0.0.0 collides with the process already on 127.0.0.1:8022)
BIND_IP=192.168.2.8

# ===== defaults below, no need to change =====

# container listen port
LISTEN_PORT=8022
# published port (use 8023 if taken, then update clients)
BRIDGE_PORT=8022
# 极影视 database directory
NATIVE_DB_DIR=/zspace/zsrp/sqlite/zvideo
LOG_LEVEL=INFO
TZ=Asia/Shanghai
# watched threshold (0~1)
PLAYED_THRESHOLD=0.9
# min seconds between DB writes
NATIVE_MIN_INTERVAL=10
# grace window for local records (seconds)
SYNC_GRACE_SECONDS=15
# sync audio/subtitle selection
SYNC_STREAM_PREFS=true
# console IP allowlist, comma separated, empty = no limit
ALLOWED_IPS=
# empty = set on first visit to /admin; or preset it (>= 6 chars)
ADMIN_PASSWORD=
```

> **Never put trailing comments in `.env`**: Compose treats ` # ...` as part of the value. `LISTEN_PORT=8022 # comment` becomes the port `8022 # comment` and startup fails with `invalid containerPort: 8022 # comment`. Put comments on their own line.

`NATIVE_MODE` / `NATIVE_DB_PATH` / `DB_PATH` are pinned in the compose `environment` block, so leave them out of `.env`.

### 3. Start

```bash
docker compose config | head -20        # variables resolved as expected?
docker compose up -d
docker compose logs -f --tail=50
curl http://192.168.2.8:8022/healthz    # expect native_mode=local
```

Open `http://192.168.2.8:8022/admin`, set the console password, then point Hills at that address.

> If the image pull times out, swap `image:` for the mirror:
> `docker.1ms.run/snarl6818/zspace-emby-bridge:latest`

### Fallback: your UI cannot create `.env`

`.env` is a dotfile and some Docker GUIs refuse to create one. You can skip it entirely and inline the values — only three spots are `[fill]`:

```yaml
services:
  bridge:
    image: snarl6818/zspace-emby-bridge:latest
    container_name: zspace-emby-bridge
    restart: unless-stopped
    ports:
      - "192.168.2.8:8022:8022"                # [fill] host IP : published port : container port
    environment:
      UPSTREAM_URL: http://192.168.2.8:8021    # [fill] 极影视 Emby endpoint
      NATIVE_USER: ""                          # [fill] ZSpace account (user_name)
      NATIVE_MODE: local
      NATIVE_DB_PATH: /zvideo/zvideo.db
      DB_PATH: /data/progress.db
      LISTEN_PORT: "8022"
      LOG_LEVEL: INFO
      TZ: Asia/Shanghai
      PLAYED_THRESHOLD: "0.9"
      NATIVE_MIN_INTERVAL: "10"
      SYNC_GRACE_SECONDS: "15"
      SYNC_STREAM_PREFS: "true"
      ALLOWED_IPS: ""
      ADMIN_PASSWORD: ""
    volumes:
      - ./config:/data
      - /zspace/zsrp/sqlite/zvideo:/zvideo
```

### Build it yourself

```bash
docker build -t zspace-emby-bridge:local .
IMAGE=zspace-emby-bridge:local docker compose up -d
```

Behind the Great Firewall:

```bash
docker build --build-arg BASE=docker.1ms.run/library/python:3.12-slim \
             --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
             -t zspace-emby-bridge:local .
```

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `UPSTREAM_URL` | `http://192.168.2.8:8021` | 极影视 Emby endpoint |
| `LISTEN_PORT` | `8022` | container listen port |
| `BRIDGE_PORT` | `8022` | host port published by compose |
| `BIND_IP` | `0.0.0.0` | host bind address (use the NAS LAN IP when 8022 is taken) |
| `NATIVE_DB_DIR` | `/zspace/zsrp/sqlite/zvideo` | directory of the 极影视 database |
| `ALLOWED_IPS` | – | console IP allowlist, comma separated |
| `DB_PATH` | `data/progress.db` | local progress database |
| `LOG_LEVEL` | `INFO` | log level (also editable in console) |
| `TZ` | `Asia/Shanghai` | timezone |
| `PLAYED_THRESHOLD` | `0.9` | watched threshold |
| `NATIVE_MODE` | `off` | `local` (mounted DB) / `ssh` (dev box) / `off` |
| `NATIVE_DB_PATH` | `/zspace/zsrp/sqlite/zvideo/zvideo.db` | inside the container: `/zvideo/zvideo.db` |
| `NATIVE_USER` | – | ZSpace account (`user_name` in `zvideo.db`), required |
| `NATIVE_MIN_INTERVAL` | `10` | min seconds between DB writes |
| `SYNC_GRACE_SECONDS` | `15` | grace window for local records |
| `SYNC_STREAM_PREFS` | `true` | sync audio/subtitle selection |
| `ADMIN_PASSWORD` | – | preset console password; empty means set it on first visit |
| `ZSPACE_SSH_HOST` / `_PORT` / `_USER` / `ZSPACE_PASS` | – | only for `NATIVE_MODE=ssh` (dev debugging) |

## Web console

Open `http://<NAS>:8022/admin`:

1. First visit asks you to set an admin password (PBKDF2, never logged); five failed logins per 10 minutes are rate-limited
2. Tune the upstream URL (applied instantly), native writes, watched threshold, write interval, sync grace, stream prefs, log level and IP allowlist; change the password; export a `.env` snippet
3. See what is playing, the latest syncs (title + file name), write counters and override/cleared events
4. Search any item by title, file name or collection_id, including its intro/outro ranges
5. Prometheus metrics at `/metrics`

## Hills setup

1. Add a server: type **Emby**, address `http://<NAS>:8022` (not 8021)
2. Use the 极影视 Emby credentials (the proxy never stores them)
3. Just play — progress is reported roughly every 11 seconds

## Acceptance checklist

| Scenario | Expected |
| --- | --- |
| Play N minutes in Hills, reopen | resumes at N |
| Play in 极影视 App, reopen in Hills | resumes where 极影视 is |
| Delete the record in 极影视, reopen Hills | progress cleared |
| Watch past 90% | 极影视 marks watched, disappears from Continue Watching |
| Movie / TV / anime / doc / custom categories | progress written (`原生进度已写` in logs) |
| 4K seek | smooth |
| Container / NAS restart | progress preserved |
| Logs | no tokens |

## Troubleshooting

| Symptom | Where to look |
| --- | --- |
| `custom validation failed: invalid volume path` | the ZSpace GUI only accepts whitelisted host paths; use the named-volume-with-bind-driver form (see the note under Layout), or an external volume |
| Hills cannot connect | `/healthz`, port mapping, firewall |
| Progress not written | log line `原生进度已写`, console toggle for native writes |
| `reason=unresolved_id` | unknown item id shape — open an issue with the id from the log |
| `reason=not_in_playlist` | item not present (and not creatable) in 极影视 |
| `原生进度写入失败` | DB path/permissions: container must run as root with the volume mapped |
| 极影视 App not refreshed | kill the app and reopen |

Read-only check on the NAS:

```bash
sudo sqlite3 'file:/zspace/zsrp/sqlite/zvideo/zvideo.db?mode=ro' \
  "SELECT collection_id, video_id, play_duration, updated_at FROM zvideo_playlist ORDER BY updated_at DESC LIMIT 5;"
```

## Known limitations

- Single user (`NATIVE_USER`)
- Intro/outro ranges are queryable in the console; this proxy does not touch Hills' skip behaviour
- A 极影视 upgrade may change the schema; writes then fail loudly in logs instead of guessing
- The proxy never parses media; only JSON control plane and byte streams

## Development

```bash
python -m pytest -q
uvicorn app.main:app --host 0.0.0.0 --port 8022
```

Version source of truth: `pyproject.toml`. Images are built by GitHub Actions on `v*` tags and pushed to Docker Hub (`linux/amd64` + `linux/arm64`).

## License

MIT, see [LICENSE](LICENSE).
