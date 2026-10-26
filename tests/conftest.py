"""测试夹具：一个 mock 极影视上游 + 真实起在后台线程里的代理实例。"""
from __future__ import annotations

import gzip
import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import Settings
from app.main import create_app


def free_port() -> int:
    """向系统要一个空闲端口，避免测试之间抢端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LiveServer:
    """在后台线程里跑一个 uvicorn 实例，测试通过真实 HTTP 访问它。"""

    def __init__(self, app: FastAPI, port: int) -> None:
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self.port = port
        self.seen: dict = {}

    def __enter__(self) -> "LiveServer":
        self._thread.start()
        deadline = time.time() + 10
        while time.time() < deadline:
            if self._server.started:
                return self
            time.sleep(0.02)
        raise RuntimeError("测试服务器启动超时")

    def __exit__(self, *exc: object) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def build_upstream() -> tuple[FastAPI, dict]:
    """模拟极影视兼容层：401/404、Range 视频流、gzip、chunked 都覆盖。"""
    app = FastAPI()
    seen: dict = {"calls": []}

    @app.get("/Users/Me")
    async def users_me() -> Response:
        seen["calls"].append({"path": "/Users/Me"})
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers={"X-Reason": "no-token"})

    @app.get("/Users/u1/Items/i1")
    async def item() -> Response:
        seen["calls"].append({"path": "/Users/u1/Items/i1"})
        return JSONResponse({"Id": "i1", "UserData": {"PlaybackPositionTicks": 500000000}})

    @app.get("/Users/u1/Items/i1/UserData")
    async def user_data() -> Response:
        return JSONResponse({"error": "not found"}, status_code=404)

    @app.get("/emby/Users/u1/Items/i1")
    async def emby_item() -> Response:
        seen["calls"].append({"path": "/emby/Users/u1/Items/i1"})
        # 上游默认「没有记录」，本地进度才应该被顶上；
        # 需要上游有记录时用 i2（带 LastPlayedDate）
        return JSONResponse(
            {
                "Id": "i1",
                "RunTimeTicks": 60000000000,
                "UserData": {"PlaybackPositionTicks": 0, "Played": bool(seen.get("played"))},
            }
        )

    @app.get("/emby/Users/u1/Items/i2")
    async def emby_item_newer() -> Response:
        # 极影视一侧更新（2030），本地记录必须让位
        return JSONResponse(
            {
                "Id": "i2",
                "RunTimeTicks": 60000000000,
                "UserData": {
                    "PlaybackPositionTicks": 12000000000,
                    "LastPlayedDate": "2030-01-01T00:00:00Z",
                },
            }
        )

    @app.get("/emby/Users/u1/Items/Resume")
    async def resume_list() -> Response:
        return JSONResponse(
            {
                "Items": [{"Id": "i1", "RunTimeTicks": 60000000000, "UserData": {"PlaybackPositionTicks": 0}}],
                "TotalRecordCount": 1,
            }
        )

    @app.post("/emby/Users/u1/PlayedItems/i1")
    async def played_items() -> Response:
        seen["calls"].append({"path": "played-items"})
        seen["played"] = True  # 模拟“回写真的生效”
        return Response(status_code=204)

    # u2：上游对 PlayedItems 一律 200 但不改状态，用来验证会换第二种写法
    @app.get("/emby/Users/u2/Items/i1")
    async def stubborn_item() -> Response:
        return JSONResponse(
            {"Id": "i1", "RunTimeTicks": 60000000000, "UserData": {"PlaybackPositionTicks": 0, "Played": False}}
        )

    @app.post("/emby/Users/u2/PlayedItems/i1")
    async def stubborn_played_prefixed() -> Response:
        seen["calls"].append({"path": "played-u2-prefixed"})
        return Response(status_code=200)

    @app.post("/Users/u2/PlayedItems/i1")
    async def stubborn_played_plain() -> Response:
        seen["calls"].append({"path": "played-u2-plain"})
        return Response(status_code=200)

    @app.api_route("/Videos/v1/stream", methods=["GET", "HEAD"])
    async def stream(request: Request) -> Response:
        payload = b"0123456789abcdef"
        rng = request.headers.get("range")
        if rng:
            start_text, _, end_text = rng.split("=")[1].partition("-")
            start = int(start_text)
            end = int(end_text) if end_text else len(payload) - 1
            part = payload[start : end + 1]
            return Response(
                part,
                status_code=206,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{len(payload)}",
                    "Accept-Ranges": "bytes",
                    "Content-Type": "video/mp4",
                },
            )
        return Response(payload, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})

    @app.get("/Gzip/Json")
    async def gzip_json() -> Response:
        body = gzip.compress(b'{"ServerName":"\\u6781\\u5f71\\u89c6"}')
        return Response(body, media_type="application/json", headers={"Content-Encoding": "gzip"})

    @app.get("/Chunked/Stream")
    async def chunked() -> Response:
        async def gen():
            for chunk in (b"aaa", b"bbb", b"ccc"):
                yield chunk

        return StreamingResponse(gen(), media_type="application/octet-stream")

    @app.post("/Sessions/Playing/Progress")
    async def progress(request: Request) -> Response:
        seen["calls"].append({"path": "/Sessions/Playing/Progress", "body": await request.json()})
        return Response(status_code=204)

    @app.post("/emby/Sessions/Playing/Progress")
    async def emby_progress(request: Request) -> Response:
        # 真实极影视对 progress 返回 400：代理仍要记账，并原样回传状态码
        seen["calls"].append({"path": "/emby/Sessions/Playing/Progress", "body": await request.json()})
        return Response(status_code=400)

    @app.get("/emby/Items/{item_id}/Images/{kind}")
    async def item_image(item_id: str, kind: str) -> Response:
        seen["calls"].append({"path": f"/emby/Items/{item_id}/Images/{kind}"})
        # 合集没封面：404；条目有封面：返回图片字节
        if item_id.startswith("collection_"):
            return Response(status_code=404)
        return Response(b"IMAGE-BYTES", media_type="image/jpeg")

    @app.get("/{path:path}")
    async def unknown(path: str) -> Response:
        seen["calls"].append({"path": f"/{path}"})
        return JSONResponse({"ok": True, "path": f"/{path}"})

    return app, seen


@pytest.fixture(scope="session")
def upstream() -> Iterator[LiveServer]:
    app, seen = build_upstream()
    with LiveServer(app, free_port()) as server:
        server.seen = seen
        yield server


@pytest.fixture()
def proxy(upstream: LiveServer) -> Iterator[LiveServer]:
    upstream.seen["calls"].clear()  # 上游是 session 级共享，逐测试清账
    upstream.seen["played"] = False
    settings = Settings(
        upstream_url=upstream.url,
        listen_port=8022,
        db_path=":memory:",
        log_level="INFO",
        tz="Asia/Shanghai",
        played_threshold=0.9,
    )
    with LiveServer(create_app(settings), free_port()) as server:
        yield server


@pytest.fixture()
def client(proxy: LiveServer) -> Iterator[httpx.Client]:
    # trust_env=False：本机 NO_PROXY 含 [::1]，httpx 解析会报 InvalidURL
    with httpx.Client(base_url=proxy.url, timeout=10.0, trust_env=False) as http:
        yield http
