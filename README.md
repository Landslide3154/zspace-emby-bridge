# zspace-emby-bridge（极影视进度桥）

在 Hills 与极影视之间加一个反向代理，把 Hills 的播放进度写回极影视，让两边进度一致、断点续播可用。不改极影视、不改 Hills。

## 为什么需要

极影视的 Emby 兼容层「读得到、写不回」（2026-10 实测，Hills Windows 1.5.5）：

- `GET /Users/{uid}/Items/{id}`、`/Items/Resume` 正常，能读到进度；
- `POST /Sessions/Playing`、`/Progress`、`/Stopped` **一律返回 400**，Hills 每 11 秒上报一次的位置被整条丢弃；
- 标准写接口 `POST /Users/{uid}/Items/{id}/UserData` 是 **404**，`PlayedItems` 只改「已看」标记、不改位置。

而极影视 App 的进度存在它自己的 SQLite 库里：`zvideo_playlist.play_duration`。本代理直接更新这张表，绕开不可用的写接口。

## 架构

```
Hills ──▶ 本代理 :8022 ──▶ 极影视 Emby :8021   读接口 / 图片 / 视频流原样透传
                    └────▶ /zspace/zsrp/sqlite/zvideo/zvideo.db   进度 / 已看
```

- **控制面**：`GET` 条目、列表、Resume 响应里的 `UserData.PlaybackPositionTicks` 用本地库重写；`Sessions/Playing*` 里的位置落本地 SQLite，并写进极影视的 `zvideo_playlist`。
- **媒体面**：视频流零拷贝流式透传，`Range` / `HEAD` / `206` 原样，不在内存里缓冲。
- **合并策略**：极影视返回的 `LastPlayedDate` 与本地 `updated_at` 比较，**取较新者**——你在极影视 App 里看得更新，Hills 就听极影视；反之亦然。

## 功能状态

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| M0 | 透传 + 日志，确认 Hills 是否真发进度 | 完成：每 11 秒一次，`PositionTicks` 准确 |
| M1 | 单条目进度存取 + 响应重写 | 完成：Hills 播 59 分钟退出，重开续播 |
| M2 | 列表/Resume 重写 + 已看回写 | 完成：首页「继续观看」显示进度，≥90% 标记已看 |
| 原生写入 | 直写 `zvideo_playlist`，极影视 App 同步显示 | 完成：两边进度双向一致 |
| M3 | Docker 化 + README + NAS 部署 | 本文件 |

## 极空间 Docker 部署

前提：极空间上 `/zspace/zsrp/sqlite/zvideo/zvideo.db` 存在（极影视装过就有）。

1. 把本仓库放到 NAS（或任意能构建的地方），复制配置：

```bash
cp .env.example .env
```

2. 编辑 `.env`，至少填 `NATIVE_USER`（极空间登录账号，也就是 `zvideo.db` 里的 `user_name`）：

```dotenv
UPSTREAM_URL=http://192.168.2.8:8021   # 极影视 Emby 接口
LISTEN_PORT=8022                        # Hills 连这个端口
NATIVE_MODE=local                       # 容器里直接写挂载的库文件
NATIVE_DB_PATH=/zvideo/zvideo.db        # 容器内路径，由 compose 映射
NATIVE_USER=你的极空间账号
PLAYED_THRESHOLD=0.9                    # 进度达到多少算「已看」
```

3. 构建并启动（极空间的 Docker/Compose 界面也可以直接粘贴 `docker-compose.yml`）：

```bash
docker compose build
docker compose up -d
docker compose logs -f --tail=100
```

4. 关键的是这一行卷映射（`docker-compose.yml` 已写好）：

```yaml
volumes:
  - /zspace/zsrp/sqlite/zvideo:/zvideo
```

容器默认以 root 运行，才能写 root 拥有的数据库文件；不要改成普通用户。

> **端口冲突**：极空间系统进程 `leds_server` 占用了 `127.0.0.1:8022`，所以 compose 里端口写成 `192.168.2.8:8022:8022`（只绑 LAN IP，仍可用 8022）。写 `8022:8022` 会报 `bind: address already in use`。

如果不用 compose，等价的手工命令：

```bash
docker run -d --name zspace-emby-bridge --restart unless-stopped \
  -p 192.168.2.8:8022:8022 \
  --env-file .env \
  -v /zspace/zsrp/sqlite/zvideo:/zvideo \
  -v zspace-emby-data:/data \
  zspace-emby-bridge:local
```

5. 健康检查：

```bash
curl http://127.0.0.1:8022/healthz
# {"status":"ok","upstream":"http://192.168.2.8:8021","native_mode":"local",...}
```

`native_mode` 必须是 `local`（容器内写库）。`off` 表示没开原生写入。

## Hills 配置

1. 在 Hills 里新增服务器：**类型 Emby**，地址填 `http://<NAS>:8022`（**不要填 8021**）。
2. 账号密码用极影视的 Emby 账号（代理不保存账号密码，只透传）。
3. 正常播放即可：Hills 每约 11 秒上报一次进度，代理据此更新本地库和极影视库。

## 验收清单

| 场景 | 期望 |
| --- | --- |
| Hills 播到 N 分钟退出，重开 | 从 N 分钟续播（读本地库） |
| 极影视 App 播到 M 分钟后，Hills 重开 | 从 M 分钟开始（服务器较新，合并策略生效） |
| Hills 播到 ≥90% 退出 | 极影视 App 显示「已看」，并从「继续观看」消失 |
| 4K 拖动进度条 | 不卡顿（`Range` 透传，代理不缓冲） |
| 重启容器 / 重启 NAS | 进度都在（本地库与极影视库都持久） |
| 看日志 | 看不到 token、api_key、Authorization |

## 故障排查

| 现象 | 先看哪里 |
| --- | --- |
| Hills 连不上 | `curl http://<NAS>:8022/healthz`；端口 8022 是否映射；极空间防火墙 |
| Hills 能播但进度不同步到极影视 | 日志有没有 `原生进度已写 collection=… pos=…s`；`/healthz` 的 `native_mode` 是否为 `local` |
| 有 `原生进度写入失败` | 库路径/权限问题：容器是否 root、卷映射是否为 `/zspace/zsrp/sqlite/zvideo:/zvideo` |
| 日志里 `原生进度未写 … reason=not_in_library` | 条目在极影视里不存在（Hills 里的 item 与极影视库对不上） |
| 进度被拉回旧值 | 合并策略取较新者：极影视 App 里有更新的播放记录就会覆盖 |
| 极影视 App 显示不同步 | App 有缓存，**彻底杀掉进程再打开** |

常用命令：

```bash
docker compose logs -f --tail=200 | grep -E '原生|progress 上报|已看'
curl -s http://127.0.0.1:8022/debug/recent?n=20     # 最近上报（已脱敏）
```

在 NAS 上手工核对（只读）：

```bash
sudo sqlite3 'file:/zspace/zsrp/sqlite/zvideo/zvideo.db?mode=ro' \
  "SELECT collection_id, play_duration, updated_at FROM zvideo_playlist ORDER BY updated_at DESC LIMIT 5;"
```

## 安全与隐私

- 凭据只放在 `.env`（已 gitignore），仓库、镜像、日志里都没有明文 token。
- 日志对 `X-Emby-Token`、`Authorization`、`api_key` 以及 query 里的同名参数统一脱敏。
- `NATIVE_MODE=ssh` 只是开发机上的临时通道（SSH + sudo 远程执行 sqlite3）；生产环境用 `local`，容器直接写挂载文件。
- 写库范围严格限定：只改 `zvideo_playlist.play_duration`、`updated_at` 和 `zvideo_list.state`，不做建表、删表、迁移。

## 已知限制

- **单用户**：`NATIVE_USER` 固定一个极空间账号；多用户需要扩展成账号映射。
- 只处理 `collection_*` 形态的 item id（极影视的影片/合集）；`parse_item_id` 解析不了的一律跳过。
- 极影视升级若改表结构，写入会失败并在日志里报 `原生进度写入失败`，不会自动改结构。
- 代理不解析视频内容，只处理 JSON 控制面与视频流透传。

## 开发

```bash
python -m pytest -q                     # 单元 + 集成测试（起 mock 上游）
uvicorn app.main:app --host 0.0.0.0 --port 8022
```

| 路径 | 作用 |
| --- | --- |
| `app/config.py` | 环境变量配置与校验 |
| `app/proxy.py` | 转发、观测、原生写入编排 |
| `app/rewrite.py` | `UserData` 重写与新旧进度合并 |
| `app/store.py` | 本地进度库（SQLite + WAL） |
| `app/native.py` | 写极影视 `zvideo_playlist` / `zvideo_list` |
| `app/redact.py` | 日志脱敏 |
| `tests/` | 单测 + 集成测试（mock 极影视 401/404/206） |
| `docs/protocol-notes.md` | 协议探测与实测记录 |

版本号唯一来源是 `pyproject.toml`。

