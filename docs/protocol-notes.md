# 极影视 Emby 兼容层探测记录

- 日期：2026-10-26
- 环境：极空间 NAS，Emby 兼容接口 `http://<NAS_IP>:8021`
- 方式：只读请求，未尝试登录。判定口径：**401 = 路由存在、需鉴权；404 = 未实现**。

## 1. 服务标识

`GET /System/Info/Public` 返回 200：

```json
{"Id":"<id>","LocalAddress":"http://<NAS_IP>:8021","ServerName":"极影视","Version":"4.7.0.0"}
```

它是一个自称 Emby 4.7.0.0 的兼容层，不是真 Emby。

## 2. 路由矩阵

| 方法 | 路径 | 结果 | 判断 |
| --- | --- | --- | --- |
| POST | `/Users/AuthenticateByName` | 400（缺账号密码） | 登录可用 |
| GET | `/Users/Me` | 401 | 可用 |
| GET | `/Users/Me/Items`、`/Users/Me/Items/Resume` | 401 | 可用 |
| GET | `/Users/{uid}/Items/{id}` | 401 | **读取条目与进度可用** |
| GET | `/Users/{uid}/Items/Resume` | 401 | 可用 |
| POST/DELETE | `/Users/{uid}/PlayedItems/{id}` | 401 | 标记已看/未看可用 |
| GET/POST | `/Items/{id}/PlaybackInfo` | 401 | 取播放地址可用 |
| GET | `/Shows/{id}/Episodes` | 401 | 可用 |
| POST | `/Sessions/Playing`、`/Sessions/Playing/Progress`、`/Sessions/Playing/Stopped` | 401 | 路由存在，但位置不落库 |
| GET | `/Videos/{id}/stream` | 自定义错误 | 串流可用 |
| GET | `/Items/{id}/Images/Primary` | 自定义错误 | 图片可用 |
| POST/GET | `/Users/{uid}/Items/{id}/UserData` | **404** | 未实现 |
| GET | `/Items/{id}` | **404** | 未实现 |
| GET | `/Sessions`、`/Users`、`/UserViews`、`/Library/MediaFolders` | **404** | 未实现 |

## 3. 推断

- 第三方客户端通过 `Sessions/Playing/Progress` 上报的 `PositionTicks` 没有被持久化；标准写接口 `UserData` 缺失，客户端没有第二条写入路径。
- 读取走 `GET /Users/{uid}/Items/{id}`，拿到的是极影视 App 写入的旧值 → 表现为“读得到、写不回”。
- 网易爆米花走极空间原生通道，与极影视双向同步正常；本项目的代理不涉及原生 API。

## 4. 复现探测

```bash
B=http://<NAS_IP>:8021
curl -s "$B/System/Info/Public"
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: application/json' -d '{}' "$B/Sessions/Playing/Progress"
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: application/json' -d '{}' "$B/Users/u1/Items/i1/UserData"
curl -s -o /dev/null -w '%{http_code}\n' "$B/Users/u1/Items/i1"
```

带鉴权查进度（API Key 只在本机用，不要写进仓库）：

```bash
curl -s "$B/Users/Me" -H "X-Emby-Token: <API_KEY>"
curl -s "$B/Users/<uid>/Items/<itemId>" -H "X-Emby-Token: <API_KEY>"
```

看返回里的 `UserData.PlaybackPositionTicks`（1 秒 = 10,000,000）。

## 5. M0 要回答的问题

1. Hills 是否真的发 `POST /Sessions/Playing/Progress`？频率如何？
2. 请求体是 JSON 还是 query？含 `ItemId`、`PositionTicks`、`PlaySessionId` 吗？
3. 退出时发的是 `Stopped` 还是别的？`PositionTicks` 是否准确？
4. Hills 读取进度时请求的是 `/Users/{uid}/Items/{id}` 还是 `/Users/Me/Items/Resume`？
5. 如果一条 progress 都没有 → 停，改走 mpv IPC/外挂播放器方案。

## 6. M0 实测结论（2026-10-26，Hills Windows 1.5.5）

方法：Hills 的服务器地址指向本机代理（`http://192.168.2.2:8022` → `http://192.168.2.8:8021`），代理以 `LOG_LEVEL=DEBUG` 记录全部请求；播放一集、拖动一次进度条、正常退出。原始日志（token 已脱敏）为本机归档 `data/proxy.m0-run1.log`、`data/proxy.m0-run2.log`（`data/` 不入库）。

| 问题 | 结论 |
| --- | --- |
| Hills 是否发 progress | **发**。`POST /emby/Sessions/Playing`（开始）、`/emby/Sessions/Playing/Progress`（播放中）、`/emby/Sessions/Playing/Stopped`（退出） |
| 频率 | Progress 约每 11 秒一次；拖动后 5.8 秒内补发一次 |
| 报文格式 | JSON body；客户端信息放在 query（`X-Emby-Authorization`、`X-Emby-Token`、`reqformat=json`） |
| 关键字段 | `ItemId`、`PositionTicks`、`PlaySessionId`、`EventName=timeupdate`、`IsPaused`、`PlayMethod=DirectStream`、`MediaSourceId`、`PlaybackRate`、`MaxStreamingBitrate` |
| PositionTicks 精度 | 与播放秒数一致：1037s → 1047s → … → `Stopped` 1094s（10,000,000 tick = 1 秒） |
| 极影视响应 | 三条路径**全部 400**，上报被整条丢弃 |
| 路径前缀 | 控制面与读取接口都带 `/emby` 前缀；播放地址 `GET /Videos/{id}/stream.mkv?Static=true…` **不带**前缀 |
| 读取进度的接口 | `GET /emby/Users/{uid}/Items/{id}`（播放前）、`GET /emby/Users/{uid}/Items/Resume`（首页续播行） |
| 视频流 | 4 次 `206 Partial Content`，Range 透传正常 |
| 其他 | `GET /emby/Items/{id}/ThumbnailSet`、`/Images/Backdrop/0` 返回 404（缺图，不影响播放）；`/emby/api/danmu/{id}` 返回 200 |

**结论**：Hills 的上报链路完整、`PositionTicks` 准确，故障点完全在极影视一侧——它对上报直接返回 400，又没有 `UserData` 写接口兜底。M0 通过，可以进入 M1。

**给 M1 的约束**：

1. 控制面与读取路径要同时匹配 `/emby/...` 与 `/...`（第一版只认 `/sessions/playing`，漏记了 14 条真实上报）。
2. 响应重写要覆盖 `GET /emby/Users/{uid}/Items/{id}`、`/Items/Resume`、`/Items`、`/Items/Latest` 的 `UserData`。
3. 日志脱敏必须覆盖 query 里的 `X-Emby-Token`：Hills 把 token 放在 query，不放 header。

