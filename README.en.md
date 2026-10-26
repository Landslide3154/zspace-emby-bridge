# zspace-emby-bridge

<img src="app/assets/icon-256.png" width="88" height="88" alt="zspace-emby-bridge icon">

**Two-way playback progress sync between Hills (any Emby client) and ZSpace's 极影视.**

极影视's Emby-compatible layer can read progress but never persists it: `Sessions/Playing*` always returns 400, `UserData` write endpoints are 404. This proxy sits in between, writes the position straight into 极影视's own SQLite database, and aligns read responses — so both sides agree, resume works, and deletions in 极影视 propagate.

中文说明: [README.md](README.md)

## Features

- **Progress sync both ways**: movies, TV, anime, documentaries, plus custom categories (抖音 / MV / 锻炼 / 和谐)
- **极影视 is authoritative**: its record wins; if it is cleared, the local copy is cleared too
- **Played sync**: marks watched past a threshold; per-episode for series, never whole-season by accident
- **Audio / subtitle preference**: writes the client's selection back to 极影视
- **Web console**: first visit asks for a password; change upstream URL, threshold, intervals, switches, log level, IP allowlist on the fly
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

## Quick start (Docker Compose)

Requires `/zspace/zsrp/sqlite/zvideo/zvideo.db` on the NAS (created by 极影视).

```yaml
services:
  bridge:
    image: zspace-emby-bridge:local
    container_name: zspace-emby-bridge
    restart: unless-stopped
    ports:
      - "${BIND_IP:-0.0.0.0}:${BRIDGE_PORT:-8022}:${LISTEN_PORT:-8022}"
    environment:
      UPSTREAM_URL: ${UPSTREAM_URL:-http://192.168.2.8:8021}
      NATIVE_MODE: local
      NATIVE_DB_PATH: /zvideo/zvideo.db
      NATIVE_USER: "${NATIVE_USER:?set your ZSpace account in .env}"
      TZ: Asia/Shanghai
      LOG_LEVEL: INFO
    volumes:
      - ./config:/data            # settings and progress DB next to compose file
      - ${NATIVE_DB_DIR:-/zspace/zsrp/sqlite/zvideo}:/zvideo
```

```bash
docker compose up -d
curl http://192.168.2.8:8022/healthz
```

`native_mode` must be `local`.

### Environment variables

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
| `PLAYED_THRESHOLD` | `0.9` | watched threshold |
| `NATIVE_MODE` | `off` | `local` / `ssh` / `off` |
| `NATIVE_DB_PATH` | `/zspace/zsrp/sqlite/zvideo/zvideo.db` | inside the container: `/zvideo/zvideo.db` |
| `NATIVE_USER` | – | ZSpace account (`user_name` in `zvideo.db`), required |
| `NATIVE_MIN_INTERVAL` | `10` | min seconds between DB writes |
| `SYNC_GRACE_SECONDS` | `15` | grace window for local records |
| `SYNC_STREAM_PREFS` | `true` | sync audio/subtitle selection |
| `ADMIN_PASSWORD` | – | preset console password; empty means set it on first visit |

## Web console

Open `http://<NAS>:8022/admin`:

1. First visit asks you to set an admin password (stored as PBKDF2, never logged)
2. Tune native writes, watched threshold, write interval, sync grace, stream prefs and log level
3. See upstream, local record count, counters and the latest syncs
4. Prometheus metrics at `/metrics`

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
| Hills cannot connect | `/healthz`, port mapping, firewall |
| Progress not written | log line `原生进度已写`, console toggle "native writes" |
| `reason=unresolved_id` | unknown item id shape — send the id from the log |
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

Version source of truth: `pyproject.toml`.
