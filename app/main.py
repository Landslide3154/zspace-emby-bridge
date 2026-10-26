"""应用装配：健康检查、观测端点、兜底透传路由。"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse

from .config import Settings
from .proxy import UpstreamProxy
from .runtime import RuntimeConfig
from .store import ProgressStore
from .web import AdminAuth, build_admin_router


def _package_version() -> str:
    """版本号唯一来源是 pyproject.toml：装进镜像后从包元数据读。"""
    try:
        from importlib.metadata import version

        return version("zspace-emby-bridge")
    except Exception:  # 源码直跑（没 pip install）时退回开发标记
        return "dev"


VERSION = _package_version()
STARTED_AT = time.monotonic()


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # 三方库会打印完整 URL 与访问行，query 里可能带 api_key，统一压到 WARNING
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("bridge").setLevel(level.upper())


def create_app(settings: Settings | None = None) -> FastAPI:
    """按给定配置装配应用；测试可注入自定义 Settings。"""
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    store = ProgressStore(settings.db_path)
    runtime = RuntimeConfig(store, settings)
    proxy = UpstreamProxy(settings, store, runtime)
    auth = AdminAuth(store, settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await proxy.aclose()
        store.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.store = store
    app.state.proxy = proxy
    app.state.runtime = runtime
    app.include_router(build_admin_router(settings, store, runtime, proxy, auth, VERSION))

    @app.get("/healthz")
    async def healthz() -> dict:
        return {
            "status": "ok",
            "upstream": settings.upstream_url,
            "version": VERSION,
            "uptime_seconds": round(time.monotonic() - STARTED_AT, 1),
            "progress_records": store.count(),
            "native_mode": settings.native_mode,
            "native_enabled": runtime.options.native_enabled,
        }

    @app.get("/debug/recent")
    async def debug_recent(n: int = 20) -> dict:
        events = store.recent(n)
        return {"count": len(events), "events": events}

    @app.websocket("/embywebsocket")
    async def emby_websocket(websocket: WebSocket) -> None:
        # M0 不转发 WebSocket：客户端会收到 1013（稍后再试），不影响播放主链路
        await websocket.accept()
        logging.getLogger("bridge.proxy").warning("WebSocket 暂未实现，直接关闭：%s", websocket.url.path)
        await websocket.close(code=1013)

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    )
    async def passthrough(path: str, request: Request):
        if request.headers.get("upgrade", "").lower() == "websocket":
            logging.getLogger("bridge.proxy").warning("收到 WebSocket 升级请求，暂不支持：%s", request.url.path)
            return JSONResponse({"error": "websocket not supported yet"}, status_code=501)
        return await proxy.handle(request)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    _settings = Settings.from_env()
    configure_logging(_settings.log_level)
    uvicorn.run(app, host="0.0.0.0", port=_settings.listen_port)
