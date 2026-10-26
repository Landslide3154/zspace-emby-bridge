# zspace-emby-bridge（极影视进度桥）— 开发约定

> 跨项目通用规则见全局 `C:\Users\godis\.dsh\AGENTS.md`，本文件不重复。
> 本机专属（NAS 地址、端口、环境版本、部署状态）见同目录 `AGENTS.local.md`，不写进本文件。

## 1. 这个项目是什么

一个反向代理：Hills（Emby 客户端）→ 本代理 → 极影视的 Emby 兼容接口，补上后者缺失的“播放进度写入”，让 Hills 能断点续播。Python 3.12 + FastAPI + httpx + SQLite，Docker 部署在极空间 NAS。

- `app/proxy.py`：请求转发、观测、写库编排与已看回写
- `app/rewrite.py`：UserData 重写（极影视为准）
- `app/store.py`：本地进度库与面板设置（SQLite，WAL）
- `app/native.py`：写极影视 `zvideo_playlist` / `zvideo_list`
- `app/runtime.py`：运行时配置（面板可改，落库）
- `app/web.py` / `app/web_ui.py`：控制台、登录、设置、指标
- `app/main.py`：路由与配置装配

（M0 前这些文件还不存在，按此边界落，不要先写成一个 `main.py`。）

## 2. 常用命令

M0 已落地，按此表执行。

| 目的 | 命令 |
| --- | --- |
| 本地跑 | `uvicorn app.main:app --host 0.0.0.0 --port 8022` |
| 测试 | `pytest -q` |
| 构建镜像 | `docker compose build` |
| 起服务 | `docker compose up -d` |
| 看日志 | `docker compose logs -f --tail=100` |
| 健康检查 | `curl -s http://127.0.0.1:8022/healthz` |

## 3. 硬约束

- 必须：先完成 M0（纯透传 + 日志），确认 Hills 真的发 `Sessions/Playing/Progress`，再写任何重写逻辑。
- 必须：视频流式透传，支持 `Range`/`HEAD`/`206`；不得把 4K 流读进内存再转发。
- 必须：`Sessions/Playing*` 里的 `PositionTicks` 落本地库；`GET /Users/{uid}/Items/{id}` 等响应的 `UserData` 用本地值重写。
- 必须：日志对 `X-Emby-Token`、`Authorization`、`api_key` 脱敏。
- 允许（用户 2026-10-26 明确授权）：写极影视数据库，但**只改** `zvideo_playlist` 的 `play_duration/updated_at/video_id/name/path/video_duration/audio_index/subtitle_index` 与 `zvideo_list.state`；不建表、不删表、不迁移。
- 禁止：修改极空间系统其它部分、逆向其原生 HTTP 接口（浏览器态签名，复刻会被 403）。
- 禁止：修改 Hills；代理必须对客户端完全透明。
- 禁止：把 API Key、账号密码写进代码、测试、compose、README。
- 禁止：上游 401/404 时伪造成功；未知路径原样透传。

## 4. 架构边界与因果

- 之所以要代理：极影视的 Emby 兼容层“读得到、写不回”——`GET /Users/{uid}/Items/{id}` 可用，但 `POST /Users/{uid}/Items/{id}/UserData` 返回 404，`Sessions/Playing/Progress` 收了不落库。取证见 `docs/protocol-notes.md`。
- 进度按 `token 哈希 + ItemId` 存本地库；**读写以极影视为准**：上游有记录就用上游，上游明确为空且本地记录超过宽限期（默认 15 秒）就删本地记录，保证「极影视删了 Hills 也清零」。
- 进度 ≥ 阈值时调用 `POST /Users/{uid}/PlayedItems/{id}` 回写“已看”（该接口存在）；这是加分项，失败不影响播放。
- 代理不解析视频内容，只处理 JSON 控制面；媒体面必须零拷贝式转发。

## 5. 版本与发布

- 版本唯一来源：`pyproject.toml` 的 `version`（M0 创建时落实），不在文档里写死版本号。
- 镜像 tag 用 `git describe --tags --always` 生成，不手写。
- 发版流程 M3 前补齐；发版前必须过 `verification-before-completion` 的验收清单。

## 6. 已知坑

- `GET /Items/{id}`、`GET /Sessions`、`GET /Users` 在极影视上是 404，客户端和测试都不要依赖。
- 上游可能返回 gzip/chunked：重写 JSON 前先解压，或请求时带 `Accept-Encoding: identity`。
- `LastPlayedDate` 可能带/不带时区：统一解析成 UTC epoch 再比较。
- 视频路由不能缓冲：`httpx` 用 `stream=True`，FastAPI 用 `StreamingResponse`。
- WebSocket `/embywebsocket` 若存在，先透传或返回 501 并在日志标注，不要让它拖垮 HTTP 路由。
- Hills 的控制面与读取接口带 `/emby` 前缀（`/emby/Sessions/Playing/Progress`、`/emby/Users/{uid}/Items/{id}`），播放地址 `GET /Videos/{id}/stream.mkv` 不带前缀；路径匹配必须两种都认。
- Hills 把 `X-Emby-Token` 放在 query 里而非 header；脱敏必须覆盖 query 参数名。
- 极影视对 `Sessions/Playing`、`/Progress`、`/Stopped` 一律返回 400（实测），进度只能落本地库，不要指望转发成功。
- M0 已实测通过（Hills 每 11 秒发一次 progress，`PositionTicks` 准确）：结论与给 M1 的路径约束见 `docs/protocol-notes.md` §6。
- 极影视的原生进度在 `zvideo_playlist.play_duration`（秒，唯一键 `user_name+classification_id+collection_id`），已看是 `zvideo_list.state=2`；库文件 `/zspace/zsrp/sqlite/zvideo/zvideo.db` 属 root:root 644，写库必须 sudo。
- 极影视 Web 的 `/zvideo/*` 接口只认浏览器会话，Python 复刻请求会被 nginx 403；**写库比逆接口稳**，不要在这上面继续绕。
- 条目 id 有两种：`collection_<collection_id>_<classification_id>`（影片/合集）与 `video_<video_id>_<collection_id>_<classification_id>`（剧集、抖音、MV、锻炼等单文件）；解析不了时用 `zvideo_list` 反查兜底。自建分类不产生新前缀。
- 控制台 `/admin`：首次访问设管理密码（PBKDF2 存库），设置写 `app_settings` 表并覆盖 env（阈值、写库间隔、宽限期、开关、日志级别），保存即生效。

## 7. 指针

- 全局规则：`C:\Users\godis\.dsh\AGENTS.md`
- 协议取证：`docs/protocol-notes.md`
- 部署与验收：`README.md`（M3 产出）
- 相关技能：`writing-plans`、`test-driven-development`、`systematic-debugging`、`verification-before-completion`、`codebase-design`
