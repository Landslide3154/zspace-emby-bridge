# zspace-emby-bridge（极影视进度桥）— 开发约定

> 跨项目通用规则见全局 `C:\Users\godis\.dsh\AGENTS.md`，本文件不重复。
> 本机专属（NAS 地址、端口、环境版本、部署状态）见同目录 `AGENTS.local.md`，不写进本文件。

## 1. 这个项目是什么

一个反向代理：Hills（Emby 客户端）→ 本代理 → 极影视的 Emby 兼容接口，补上后者缺失的“播放进度写入”，让 Hills 能断点续播。Python 3.12 + FastAPI + httpx + SQLite，Docker 部署在极空间 NAS。

- `app/proxy.py`：请求转发与视频流式透传
- `app/rewrite.py`：UserData 重写与新旧进度合并
- `app/store.py`：进度存储（SQLite，WAL）
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
- 禁止：修改极影视/极空间系统、写它的数据库、逆向其原生 API。
- 禁止：修改 Hills；代理必须对客户端完全透明。
- 禁止：把 API Key、账号密码写进代码、测试、compose、README。
- 禁止：上游 401/404 时伪造成功；未知路径原样透传。

## 4. 架构边界与因果

- 之所以要代理：极影视的 Emby 兼容层“读得到、写不回”——`GET /Users/{uid}/Items/{id}` 可用，但 `POST /Users/{uid}/Items/{id}/UserData` 返回 404，`Sessions/Playing/Progress` 收了不落库。取证见 `docs/protocol-notes.md`。
- 进度按 `token 哈希 + ItemId` 存；合并时比较极影视返回的 `LastPlayedDate` 与本地 `updated_at`，取较新者，避免把用户在极影视 App 里的新进度拉回去。
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

## 7. 指针

- 全局规则：`C:\Users\godis\.dsh\AGENTS.md`
- 协议取证：`docs/protocol-notes.md`
- 部署与验收：`README.md`（M3 产出）
- 相关技能：`writing-plans`、`test-driven-development`、`systematic-debugging`、`verification-before-completion`、`codebase-design`
