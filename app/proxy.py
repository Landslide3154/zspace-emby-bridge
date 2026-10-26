"""请求转发与观测：进度落本地库，读条目时把本地进度写回响应。"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

from .config import Settings
from .native import build_writer, parse_item_id
from .redact import redact_json, redact_url
from .rewrite import LocalProgress, collect_runtimes, is_rewritable_path, rewrite_payload
from .store import ProgressStore, token_hash

logger = logging.getLogger("bridge.proxy")

# 控制面：Sessions/Playing、/Progress、/Stopped 都以此前缀开头
CONTROL_PREFIX = "/sessions/playing"

_TOKEN_IN_AUTH = re.compile(r'Token="?([^",]+)"?', re.IGNORECASE)
_USER_IN_PATH = re.compile(r"^/(?:emby/)?users/([^/]+)/", re.IGNORECASE)


def extract_token(request: Request) -> str | None:
    """Hills 把 token 放 query（实测），标准 Emby 客户端放 header，两种都认。"""
    for params in (request.query_params, request.headers):
        for key, value in params.items():
            if key.lower() in ("x-emby-token", "x-mediabrowser-token") and value:
                return value
    authorization = request.headers.get("authorization") or request.query_params.get("X-Emby-Authorization") or ""
    match = _TOKEN_IN_AUTH.search(authorization)
    return match.group(1) if match else None


def extract_user_id(path: str, query: str = "") -> str | None:
    """用户 id：优先路径里的 {uid}，否则取 query 的 UserId（Hills 的 Sessions/* 走这条）。"""
    match = _USER_IN_PATH.match(path)
    if match is not None:
        user = match.group(1)
        return None if user.lower() == "me" else user
    for key, values in parse_qs(query, keep_blank_values=True).items():
        if key.lower() == "userid" and values:
            return values[0]
    return None

# 逐跳头不能转发，否则破坏连接语义
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    }
)


@dataclass(frozen=True)
class ProgressEvent:
    """一次 Sessions/Playing* 上报的观测结果。"""

    method: str
    path: str
    item_id: str | None
    position_ticks: int | None
    play_session_id: str | None
    has_position_ticks: bool
    body_format: str
    body_summary: str
    received_at: float
    audio_index: int | None = None
    subtitle_index: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "item_id": self.item_id,
            "position_ticks": self.position_ticks,
            "has_position_ticks": self.has_position_ticks,
            "play_session_id": self.play_session_id,
            "body_format": self.body_format,
            "body_summary": self.body_summary,
            "audio_index": self.audio_index,
            "subtitle_index": self.subtitle_index,
            "received_at": datetime.fromtimestamp(self.received_at, UTC).isoformat(),
        }


def _as_int(value: Any) -> int | None:
    """PositionTicks 可能是 int、float 或字符串；0 是合法值，不能当成缺失。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


def is_control_path(path: str) -> bool:
    """Sessions/Playing* 判定：Hills 走 /emby 前缀（实测），同时兼容无前缀。"""
    normalized = path.lower().rstrip("/")
    return any(normalized.startswith(base + CONTROL_PREFIX) for base in ("/emby", ""))


def parse_progress_event(method: str, path: str, query: str, body: bytes) -> ProgressEvent | None:
    """识别 Sessions/Playing* 上报并抽出关键字段；非控制面返回 None。"""
    if method.upper() != "POST":
        return None
    if not is_control_path(path):
        return None

    data: dict[str, Any] = {}
    body_format = "empty"
    if body:
        try:
            parsed = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            data, body_format = parsed, "json"

    if body_format != "json" and query:
        pairs = parse_qs(query, keep_blank_values=True)
        flat = {key: values[-1] for key, values in pairs.items() if values}
        if flat:
            data, body_format = flat, "query"

    ticks = _as_int(data.get("PositionTicks"))
    item_id = data.get("ItemId") or data.get("itemId")
    play_session_id = data.get("PlaySessionId") or data.get("playSessionId")
    audio_index = _as_int(data.get("AudioStreamIndex"))
    subtitle_index = _as_int(data.get("SubtitleStreamIndex"))
    body_summary = _summarize(data)
    return ProgressEvent(
        method=method.upper(),
        path=path,
        item_id=str(item_id) if item_id is not None else None,
        position_ticks=ticks,
        play_session_id=str(play_session_id) if play_session_id is not None else None,
        has_position_ticks=ticks is not None,
        body_format=body_format,
        body_summary=body_summary,
        received_at=time.time(),
        audio_index=audio_index,
        subtitle_index=subtitle_index,
    )


def _summarize(data: dict[str, Any]) -> str:
    """给日志留一份脱敏、截断的请求体摘要，便于事后确认字段名。"""
    if not data:
        return ""
    try:
        text = json.dumps(redact_json(data), ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        text = str(sorted(data))
    return text[:400]


# 响应方向要把 Content-Length 留下：HEAD 与 Range 都靠它，客户端会校验
# date/server 由本进程重新生成，原样转发会出现重复头
RESPONSE_DROP = HOP_BY_HOP - {"content-length"} | {"date", "server"}


class UpstreamProxy:
    """把请求转给极影视：进度落本地库，读条目时把本地进度写回响应。"""

    def __init__(self, settings: Settings, store: ProgressStore, runtime: RuntimeConfig | None = None) -> None:
        self._settings = settings
        self._store = store
        self._runtime = runtime
        self.stats: dict[str, float] = {"progress": 0, "native_written": 0, "native_failed": 0, "played": 0,
                                       "last_progress_at": 0.0, "last_native_at": 0.0}
        self._tasks: set[asyncio.Task] = set()
        self._writer = build_writer(
            settings.native_mode,
            db_path=settings.native_db_path,
            user_name=settings.native_user,
            host=settings.ssh_host,
            port=settings.ssh_port,
            ssh_user=settings.ssh_user,
            password=settings.ssh_password,
        )
        self._last_native: dict[str, float] = {}
        self._client = httpx.AsyncClient(
            base_url=settings.upstream_url,
            # read 不设上限：暂停播放时连接会长时间空闲，超时会把视频流掐断
            timeout=httpx.Timeout(connect=10.0, read=None, write=60.0, pool=10.0),
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=8),
            follow_redirects=False,
            # 纯局域网：不吃系统代理环境变量（本机 NO_PROXY 里的 [::1] 还会让 httpx 解析报错）
            trust_env=False,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def writer(self):
        return self._writer

    @property
    def _options(self):
        return self._runtime.options if self._runtime is not None else None

    def _option(self, name: str, default):
        options = self._options
        return getattr(options, name, default) if options is not None else default

    async def handle(self, request: Request) -> Response:
        started = time.perf_counter()
        body = await request.body()
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")

        token = extract_token(request)
        token_id = token_hash(token) if token else ""
        user_id = extract_user_id(request.url.path, request.url.query)

        event = parse_progress_event(request.method, request.url.path, request.url.query, body)
        if event is not None:
            self._record(event, token_id, user_id)
            self._maybe_write_back(event, token_id, user_id, token)
            self._sync_native(event)

        headers = {key: value for key, value in request.headers.items() if key.lower() not in HOP_BY_HOP}
        outgoing = self._client.build_request(request.method, target, headers=headers, content=body)
        try:
            upstream = await self._client.send(outgoing, stream=True)
        except httpx.TimeoutException:
            logger.warning("上游超时 %s %s", request.method, redact_url(request.url.path))
            return JSONResponse({"error": "upstream timeout"}, status_code=504)
        except httpx.ConnectError:
            logger.error("上游连不上 %s %s", request.method, redact_url(request.url.path))
            return JSONResponse({"error": "upstream unreachable"}, status_code=502)
        except httpx.HTTPError as exc:
            logger.error("上游请求失败 %s %s: %s", request.method, redact_url(request.url.path), type(exc).__name__)
            return JSONResponse({"error": f"upstream error: {type(exc).__name__}"}, status_code=502)

        logger.debug(
            "%s %s -> %s %.1fms",
            request.method,
            redact_url(target),
            upstream.status_code,
            (time.perf_counter() - started) * 1000,
        )
        if self._should_rewrite(request, upstream, token_id):
            return await self._rewritten(upstream, token_id)

        response_headers = {key: value for key, value in upstream.headers.items() if key.lower() not in RESPONSE_DROP}
        return StreamingResponse(
            upstream.aiter_raw(),
            status_code=upstream.status_code,
            headers=response_headers,
            background=BackgroundTask(upstream.aclose),
        )

    def _should_rewrite(self, request: Request, upstream: httpx.Response, token_id: str) -> bool:
        """只改写 JSON 控制面响应；视频流永远走流式透传。"""
        return (
            request.method.upper() == "GET"
            and token_id != ""
            and upstream.status_code == 200
            and is_rewritable_path(request.url.path)
            and "json" in upstream.headers.get("content-type", "").lower()
        )

    async def _rewritten(self, upstream: httpx.Response, token_id: str) -> Response:
        """读完整 JSON 后按本地进度重写；体积只涉及控制面，不碰媒体流。"""
        raw = await upstream.aread()
        await upstream.aclose()
        headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in RESPONSE_DROP and key.lower() not in {"content-length", "content-encoding"}
        }
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(content=raw, status_code=upstream.status_code, headers=headers)
        rewritten = rewrite_payload(
            payload,
            lambda item_id: self._local_progress(token_id, item_id),
            grace=self._option('sync_grace_seconds', 15.0),
            on_clear=lambda item_id: self._store.delete(token_id, item_id),
        )
        runtimes = collect_runtimes(rewritten)
        if runtimes:
            self._store.save_runtimes(runtimes)
            logger.debug("缓存时长 %s", {key: round(value / 1e7, 1) for key, value in runtimes.items()})
        data = json.dumps(rewritten, ensure_ascii=False).encode("utf-8")
        headers["content-type"] = "application/json; charset=utf-8"
        return Response(content=data, status_code=upstream.status_code, headers=headers)

    def _local_progress(self, token_id: str, item_id: str) -> LocalProgress | None:
        record = self._store.get(token_id, item_id)
        if record is None:
            return None
        logger.debug("本地进度命中 item=%s ticks=%s updated_at=%s", item_id, record.position_ticks, record.updated_at)
        return LocalProgress(position_ticks=record.position_ticks, updated_at=record.updated_at, played=record.played)

    def _record(self, event: ProgressEvent, token_id: str, user_id: str | None) -> None:
        """落库 + 留一条脱敏日志；没有 token 时不落库，避免多用户串号。"""
        self.stats["progress"] += 1
        self.stats["last_progress_at"] = time.time()
        if token_id:
            self._store.record(event, token_id, user_id)
        logger.info(
            "progress 上报 %s %s item=%s ticks=%s has_position_ticks=%s format=%s session=%s user=%s body=%s",
            event.method,
            event.path,
            event.item_id,
            event.position_ticks,
            event.has_position_ticks,
            event.body_format,
            event.play_session_id,
            user_id,
            event.body_summary,
        )

    def _maybe_write_back(
        self, event: ProgressEvent, token_id: str, user_id: str | None, token: str | None
    ) -> None:
        if not token or not user_id or not event.item_id or event.position_ticks is None:
            return
        runtime = self._store.get_runtime(event.item_id)
        if runtime is None or runtime <= 0:
            return
        if event.position_ticks / runtime < self._option('played_threshold', 0.9):
            return
        if not self._store.claim_played(token_id, event.item_id):
            return
        self.stats["played"] += 1
        parsed = parse_item_id(event.item_id)
        if parsed is not None and self._writer is not None:
            mark_task = asyncio.create_task(self._mark_native_played(event.item_id))
            self._tasks.add(mark_task)
            mark_task.add_done_callback(self._tasks.discard)
        task = asyncio.create_task(self._post_played(user_id, event.item_id, token))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _sync_native(self, event: ProgressEvent) -> None:
        """把位置写进极影视自己的库：节流写，Stopped 必写。"""
        if self._writer is None or not event.item_id or event.position_ticks is None:
            return
        if not self._option("native_enabled", True):
            return
        seconds = event.position_ticks // 10_000_000
        stopped = event.path.rstrip("/").lower().endswith("/stopped")
        now = time.monotonic()
        if not stopped and now - self._last_native.get(event.item_id, 0.0) < self._option('native_min_interval', 10.0):
            return
        self._last_native[event.item_id] = now
        task = asyncio.create_task(self._write_native(event, seconds))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _write_native(self, event: ProgressEvent, seconds: int) -> None:
        item = await asyncio.to_thread(self._writer.resolve, event.item_id or "")
        if item is None:
            logger.debug("原生进度未写 item=%s reason=unresolved_id", event.item_id)
            return
        prefs = self._option('sync_stream_prefs', True)
        audio_index = event.audio_index if prefs else None
        subtitle_index = event.subtitle_index if prefs else None
        try:
            result = await asyncio.to_thread(
                self._writer.write_position,
                item,
                seconds,
                audio_index=audio_index,
                subtitle_index=subtitle_index,
            )
        except Exception as exc:  # 原生写入失败不能影响播放
            self.stats["native_failed"] += 1
            logger.warning("原生进度写入失败 collection=%s: %s", item.collection_id, type(exc).__name__)
            return
        if result.changed:
            self.stats["native_written"] += 1
            self.stats["last_native_at"] = time.time()
            logger.info(
                "原生进度已写 collection=%s video=%s pos=%ss", item.collection_id, item.video_id or "-", seconds
            )
        else:
            logger.debug("原生进度未写 collection=%s reason=%s", item.collection_id, result.reason)

    async def _mark_native_played(self, item_id: str) -> None:
        item = await asyncio.to_thread(self._writer.resolve, item_id)
        if item is None:
            logger.debug("原生已看未写 item=%s reason=unresolved_id", item_id)
            return
        try:
            result = await asyncio.to_thread(self._writer.mark_played, item)
        except Exception as exc:
            logger.warning("原生已看写入失败 collection=%s: %s", item.collection_id, type(exc).__name__)
            return
        if result.changed:
            logger.info("原生已看已写 collection=%s video=%s", item.collection_id, item.video_id or "-")
        else:
            logger.debug("原生已看未写 collection=%s reason=%s", item.collection_id, result.reason)

    async def _post_played(self, user_id: str, item_id: str, token: str) -> None:
        """后台回写“已看”：写完必须回读确认，200 不等于生效（极影视实测）。"""
        headers = {"X-Emby-Token": token}
        candidates = (
            f"/emby/Users/{user_id}/PlayedItems/{item_id}",
            f"/Users/{user_id}/PlayedItems/{item_id}",
        )
        for path in candidates:
            try:
                response = await self._client.post(path, headers=headers, timeout=5.0)
            except httpx.HTTPError as exc:
                logger.warning("已看回写请求失败 %s: %s", path, type(exc).__name__)
                continue
            confirmed = await self._upstream_played(user_id, item_id, headers)
            logger.info("已看回写 %s -> %s，上游确认=%s", path, response.status_code, confirmed)
            if confirmed:
                return
        logger.warning("已看回写未生效 item=%s：两种写法都没改变上游状态", item_id)

    async def _upstream_played(self, user_id: str, item_id: str, headers: dict[str, str]) -> bool | None:
        """回读上游条目的 UserData：确认真写了进去，而不是只看 200。"""
        try:
            response = await self._client.get(f"/emby/Users/{user_id}/Items/{item_id}", headers=headers, timeout=5.0)
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("UserData"), dict):
            return None
        user_data = payload["UserData"]
        logger.debug(
            "上游状态 item=%s played=%s pos=%s last=%s",
            item_id,
            user_data.get("Played"),
            user_data.get("PlaybackPositionTicks"),
            user_data.get("LastPlayedDate"),
        )
        return bool(user_data.get("Played"))
