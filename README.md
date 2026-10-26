# 极影视进度桥 · zspace-emby-bridge

<img src="app/assets/icon-256.png" width="88" height="88" alt="极影视进度桥图标">

**让 Hills（以及任何 Emby 客户端）的播放进度与极影视双向同步。**

极影视的 Emby 兼容层「读得到、写不回」：进度接口一律 400，写接口 404。本代理挂在中间，把播放位置直接写进极影视自己的数据库，并在读接口上做对齐，于是两边进度一致、断点续播可用；极影视 App 里删除记录也会同步清掉。

[English](README.en.md) · [Docker Hub](https://hub.docker.com/r/snarl6818/zspace-emby-bridge) · [反馈问题](https://github.com/Landslide3154/zspace-emby-bridge/issues)

## 特性

- **进度双向同步**：电影、电视剧、动画、纪录片，以及自建的其它分类全部覆盖
- **以极影视为准**：极影视里的记录就是真相，删除会同步（不再把旧进度塞回客户端）
- **已看同步**：进度过阈值自动标记已看；剧集按集标记，整季标记也不会误伤
- **音轨 / 字幕偏好**：把客户端的音轨与字幕选择写回极影视
- **网页控制台**：首次打开设密码；可改上游地址、阈值、写入间隔、开关、日志级别、IP 白名单，即时生效
- **看得懂**：同步记录显示片名与文件名，可按片名/文件名/collection_id 搜索
- **可诊断**：一键测试上游连通性、记录「被极影视覆盖 / 被清空」事件、显示正在播放的条目
- **视频流零拷贝**：Range / HEAD / 206 原样透传，4K 拖动不额外占内存
- **脱敏**：日志里不会出现 token、Authorization、api_key

## 架构

```
Hills ──▶ 本代理 :8022 ──▶ 极影视 Emby :8021   读接口 / 图片 / 视频流原样透传
                    └────▶ zvideo.db             进度、已看、音轨/字幕偏好
```

- 控制面：读接口里的 `UserData` 用极影视库里的真实值对齐；播放上报（`Sessions/Playing*`）解析后写进 `zvideo_playlist`
- 媒体面：视频流不缓冲、不解码，原样流式转发
- 同步规则：**极影视有记录 → 以它为准**；极影视明确为空且本地记录已过期（默认 15 秒宽限）→ 认为那边删了，本地跟着清

## 快速开始

前提：宿主机上有极影视的库 `/zspace/zsrp/sqlite/zvideo/zvideo.db`（装过极影视就有）。容器以 root 运行才能写它，Docker 默认就是 root。

### 目录结构

`.env` 必须和 `docker-compose.yml` 在**同一个目录**（`env_file` 和 `${...}` 插值都相对 compose 文件所在目录解析）：

```
<项目目录>/
├── docker-compose.yml
├── .env                ← 和 compose 同级，文件名必须是 .env
└── config/             ← 首次启动自动生成：面板密码、进度库
```

极空间上用 Docker 界面建的项目，目录一般是
`/tmp/zfsv3/nvme12/<账号>/data/docker/<项目名>/`（和 jackett、komga 同级）。

### 1. `docker-compose.yml`（注释版，复制即用）

```yaml
services:
  bridge:
    # 能直连 Docker Hub 用这个；拉取超时就换 docker.1ms.run/snarl6818/zspace-emby-bridge:latest
    image: snarl6818/zspace-emby-bridge:latest
    container_name: zspace-emby-bridge
    restart: unless-stopped
    ports:
      # 三个变量都从 .env 读。BIND_IP 留空会绑 0.0.0.0，
      # 撞上系统已占用的 127.0.0.1:8022 就起不来
      - "${BIND_IP:-0.0.0.0}:${BRIDGE_PORT:-8022}:${LISTEN_PORT:-8022}"
    env_file:
      - .env                                  # 变量与账号都在这里
    environment:
      NATIVE_MODE: local                      # 容器内直接写极影视的库
      NATIVE_DB_PATH: /zvideo/zvideo.db       # 容器内路径，对应下面的挂载
      DB_PATH: /data/progress.db              # 本地进度库，落在 ./config 里
    volumes:
      - ./config:/data                        # 配置与进度库，跟 compose 同目录
      # NATIVE_DB_DIR 默认就是极空间的库目录，一般不用改
      - ${NATIVE_DB_DIR:-/zspace/zsrp/sqlite/zvideo}:/zvideo
```

### 2. `.env`（注释版，只有三项必填）

```ini
# ===== 必填三项 =====

# 【必填 1】极影视的 Emby 接口地址
UPSTREAM_URL=http://192.168.2.8:8021

# 【必填 2】极空间账号（极影视库里的 user_name）
NATIVE_USER=

# 【必填 3】绑定地址：极空间上必须写本机 LAN IP
# （写 0.0.0.0 会和系统进程抢 127.0.0.1:8022，启动失败）
BIND_IP=192.168.2.8

# ===== 以下保持默认即可 =====

# 容器内监听端口
LISTEN_PORT=8022
# 对外端口（被占就改 8023，客户端地址同步改）
BRIDGE_PORT=8022
# 极影视库目录
NATIVE_DB_DIR=/zspace/zsrp/sqlite/zvideo
LOG_LEVEL=INFO
TZ=Asia/Shanghai
# 已看阈值（0~1）
PLAYED_THRESHOLD=0.9
# 写库最小间隔（秒）
NATIVE_MIN_INTERVAL=10
# 本地记录宽限期（秒）
SYNC_GRACE_SECONDS=15
# 是否同步音轨/字幕偏好
SYNC_STREAM_PREFS=true
# 面板 IP 白名单，逗号分隔，留空不限制
ALLOWED_IPS=
# 留空＝首次打开 /admin 时设置；也可直接填 ≥6 位
ADMIN_PASSWORD=
```

> **`.env` 里不要写行尾注释**：Compose 会把 ` # ...` 一起当成值。写成 `LISTEN_PORT=8022 # 容器内监听端口` 会让端口变成 `8022 # 容器内监听端口`，启动时报
> `invalid containerPort: 8022 # 容器内监听端口`。注释一律**另起一行**。

`NATIVE_MODE` / `NATIVE_DB_PATH` / `DB_PATH` 已经在 compose 的 `environment` 里固定，不用写进 `.env`（写了也会被那三行覆盖）。

### 3. 启动

```bash
docker compose config | head -20        # 确认 BIND_IP / UPSTREAM_URL 已代入
docker compose up -d
docker compose logs -f --tail=50        # 看有没有报错
curl http://192.168.2.8:8022/healthz    # 应返回 native_mode=local
```

首次打开 `http://192.168.2.8:8022/admin` 设管理密码，再把客户端指向这个地址。

> 拉镜像超时（国内常见）就把 `image:` 换成镜像站：
> `docker.1ms.run/snarl6818/zspace-emby-bridge:latest`

### 兜底：界面里不方便创建 `.env`

`.env` 是隐藏文件，有些 Docker 图形界面不好新建。这种情况可以不用 `.env`，把值直接写进 compose，效果完全一样——只有三处 `【填】`：

```yaml
services:
  bridge:
    image: snarl6818/zspace-emby-bridge:latest
    container_name: zspace-emby-bridge
    restart: unless-stopped
    ports:
      - "192.168.2.8:8022:8022"                # 【填】本机 IP : 对外端口 : 容器端口
    environment:
      UPSTREAM_URL: http://192.168.2.8:8021    # 【填】极影视 Emby 接口
      NATIVE_USER: ""                          # 【填】极空间账号（user_name）
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

### 自己构建

```bash
docker build -t zspace-emby-bridge:local .
IMAGE=zspace-emby-bridge:local docker compose up -d
```

国内网络（换镜像站）：

```bash
docker build --build-arg BASE=docker.1ms.run/library/python:3.12-slim \
             --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
             -t zspace-emby-bridge:local .
```

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `UPSTREAM_URL` | `http://192.168.2.8:8021` | 极影视 Emby 接口 |
| `LISTEN_PORT` | `8022` | 容器内监听端口 |
| `BRIDGE_PORT` | `8022` | 宿主对外端口（compose 用） |
| `BIND_IP` | `0.0.0.0` | 宿主绑定地址；极空间上常写 `192.168.2.8` 避开系统占用 |
| `NATIVE_DB_DIR` | `/zspace/zsrp/sqlite/zvideo` | 极影视库目录（compose 挂载用） |
| `ALLOWED_IPS` | 空 | 面板 IP 白名单，逗号分隔 |
| `DB_PATH` | `data/progress.db` | 本地进度库（写入缓冲/兜底） |
| `LOG_LEVEL` | `INFO` | 日志级别，面板可改 |
| `TZ` | `Asia/Shanghai` | 时区 |
| `PLAYED_THRESHOLD` | `0.9` | 已看阈值，面板可改 |
| `NATIVE_MODE` | `off` | `local`（容器挂库）/ `ssh`（开发机）/ `off` |
| `NATIVE_DB_PATH` | `/zspace/zsrp/sqlite/zvideo/zvideo.db` | 容器内是 `/zvideo/zvideo.db` |
| `NATIVE_USER` | 空 | 极空间账号（`zvideo.db` 里的 `user_name`），必填 |
| `NATIVE_MIN_INTERVAL` | `10` | 写库最小间隔（秒） |
| `SYNC_GRACE_SECONDS` | `15` | 本地记录宽限期 |
| `SYNC_STREAM_PREFS` | `true` | 是否同步音轨/字幕偏好 |
| `ADMIN_PASSWORD` | 空 | 预置面板密码；留空则首次打开面板时设置 |
| `ZSPACE_SSH_HOST` / `_PORT` / `_USER` / `ZSPACE_PASS` | 空 | 仅 `NATIVE_MODE=ssh` 时需要（开发机调试通道） |

## 网页控制台

打开 `http://<NAS>:8022/admin`：

1. **首次打开**会要求设置管理密码（至少 6 位，PBKDF2 存库，不入日志）
2. 登录后可改：**上游地址（即时生效）**、原生写入开关、已看阈值、写库间隔、同步宽限、音轨字幕同步、日志级别、IP 白名单；还能改管理密码、导出 `.env` 片段
3. 概览页能看到：正在播放的条目、最近同步（片名 + 文件名）、写库计数，以及「被极影视覆盖 / 被清空」事件
4. 「工具」页支持用片名、文件名或 collection_id 查询条目与片头片尾区间
5. `/metrics` 提供 Prometheus 文本指标；登录失败 5 次/10 分钟会限流

## Hills 配置

1. 新增服务器：类型 **Emby**，地址 `http://<NAS>:8022`（不要填 8021）
2. 账号密码用极影视那套（代理不保存账号密码，只透传）
3. 正常播放即可，每约 11 秒上报一次进度

## 验收清单

| 场景 | 期望 |
| --- | --- |
| Hills 播 N 分钟退出，重开 | 从 N 分钟续播 |
| 极影视 App 播 M 分钟后 Hills 重开 | 从 M 开始（以极影视为准） |
| 极影视里删除观看记录后 Hills 重开 | 进度清零，不再显示旧位置 |
| 播到 ≥90% 退出 | 极影视显示已看，并从继续观看消失 |
| 电影 / 电视剧 / 动画 / 纪录片 / 自建分类 | 进度都能写回（日志 `原生进度已写`） |
| 4K 拖动进度条 | 不卡顿 |
| 重启容器 / 重启 NAS | 进度都在 |
| 看日志 | 没有 token、api_key、Authorization |

## 故障排查

| 现象 | 先看哪里 |
| --- | --- |
| Hills 连不上 | `/healthz`、端口 8022 是否映射、防火墙 |
| 进度不同步到极影视 | 日志有没有 `原生进度已写`；面板里「原生进度写入」是否开着 |
| 日志 `原生进度未写 … reason=unresolved_id` | 该条目的 id 形态没认出来，把日志里的 item 发到 issues |
| 日志 `原生进度未写 … reason=not_in_playlist` | 极影视里没有这条记录（也没能建档） |
| `原生进度写入失败` | 库路径/权限：容器是否 root、卷映射是否正确 |
| 极影视 App 不同步 | App 有缓存，彻底杀掉进程再打开 |

手工核对（NAS 上只读）：

```bash
sudo sqlite3 'file:/zspace/zsrp/sqlite/zvideo/zvideo.db?mode=ro' \
  "SELECT collection_id, video_id, play_duration, updated_at FROM zvideo_playlist ORDER BY updated_at DESC LIMIT 5;"
```

## 已知限制

- **单用户**：`NATIVE_USER` 固定一个极空间账号
- **片头片尾**：只提供查询（面板与 API），本代理不介入 Hills 的跳过逻辑
- **极影视升级**可能改表结构，写入会失败并打日志，不会自动改结构
- 代理不解析视频内容，只处理 JSON 控制面与视频流透传

## 开发

```bash
python -m pytest -q
uvicorn app.main:app --host 0.0.0.0 --port 8022
```

| 路径 | 作用 |
| --- | --- |
| `app/config.py` | 环境变量与校验 |
| `app/runtime.py` | 运行时配置（面板可改，落库） |
| `app/proxy.py` | 转发、观测、写库编排、已看回写 |
| `app/rewrite.py` | `UserData` 重写 |
| `app/store.py` | 本地进度库（SQLite + WAL） |
| `app/native.py` | 写 `zvideo_playlist` / `zvideo_list` |
| `app/web.py` / `app/web_ui.py` | 控制台与指标 |
| `app/redact.py` | 日志脱敏 |
| `docs/protocol-notes.md` | 协议探测与实测记录 |

版本号唯一来源：`pyproject.toml`。镜像由 GitHub Actions 在推 `v*` 标签时构建并推送到 Docker Hub（`linux/amd64` + `linux/arm64`）。

## 许可证

MIT，见 [LICENSE](LICENSE)。

