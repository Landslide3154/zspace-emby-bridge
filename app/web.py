"""控制台：首次设置密码、登录、设置、状态、Prometheus 指标。"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any

from fastapi import APIRouter, Request
from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

from .config import Settings
from .runtime import RuntimeConfig
from .store import ProgressStore
from .web_ui import ADMIN_HTML

ASSETS = Path(__file__).parent / "assets"
COOKIE_NAME = "bridge_admin"
SESSION_TTL = 7 * 24 * 3600
PASSWORD_KEY = "admin_password"
SECRET_KEY = "admin_secret"
MIN_PASSWORD = 6


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()
    return f"{salt}${digest}"


def verify_password(stored: str, password: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()
    return hmac.compare_digest(digest, candidate)


class AdminAuth:
    """单管理员密码：首次由面板设置，也可以用 ADMIN_PASSWORD 预置。"""

    def __init__(self, store: ProgressStore, settings: Settings) -> None:
        self._store = store
        stored = store.get_settings()
        if PASSWORD_KEY not in stored and settings.admin_password:
            store.put_settings(
                {PASSWORD_KEY: hash_password(settings.admin_password), SECRET_KEY: secrets.token_hex(32)}
            )
        self._password = ""
        self._secret = ""
        self._load()

    def _load(self) -> None:
        stored = self._store.get_settings()
        self._password = stored.get(PASSWORD_KEY, "")
        self._secret = stored.get(SECRET_KEY, "")

    @property
    def needs_setup(self) -> bool:
        return not self._password

    def setup(self, password: str) -> None:
        if len(password) < MIN_PASSWORD:
            raise ValueError(f"密码至少 {MIN_PASSWORD} 位")
        self._store.put_settings(
            {PASSWORD_KEY: hash_password(password), SECRET_KEY: secrets.token_hex(32)}
        )
        self._load()

    def login(self, password: str) -> str | None:
        if not self._password or not verify_password(self._password, password):
            return None
        issued = str(int(time.time()))
        signature = hmac.new(self._secret.encode("utf-8"), issued.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{issued}.{signature}"

    def check(self, token: str | None) -> bool:
        if not token or "." not in token or not self._secret:
            return False
        issued, signature = token.split(".", 1)
        expected = hmac.new(self._secret.encode("utf-8"), issued.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        try:
            return time.time() - int(issued) <= SESSION_TTL
        except ValueError:
            return False


def build_admin_router(
    settings: Settings,
    store: ProgressStore,
    runtime: RuntimeConfig,
    proxy: Any,
    auth: AdminAuth,
    version: str,
) -> APIRouter:
    router = APIRouter()

    def authenticated(request: Request) -> bool:
        return auth.check(request.cookies.get(COOKIE_NAME))

    def guard(request: Request) -> JSONResponse | None:
        if not authenticated(request):
            return JSONResponse({"detail": "请先登录"}, status_code=401)
        if request.method not in {"GET", "HEAD"} and request.headers.get("x-requested-with") != "fetch":
            return JSONResponse({"detail": "缺少 X-Requested-With"}, status_code=400)
        return None

    @router.get("/admin", response_class=HTMLResponse)
    async def admin_page() -> HTMLResponse:
        return HTMLResponse(ADMIN_HTML)

    @router.get("/icon.png")
    async def icon_png() -> FileResponse:
        return FileResponse(ASSETS / "icon-256.png", media_type="image/png")

    @router.get("/icon-192.png")
    async def icon_192() -> FileResponse:
        return FileResponse(ASSETS / "icon-192.png", media_type="image/png")

    @router.get("/favicon.ico")
    async def favicon() -> FileResponse:
        return FileResponse(ASSETS / "icon-64.png", media_type="image/png")

    @router.get("/admin/api/session")
    async def session(request: Request) -> dict:
        return {
            "authenticated": authenticated(request),
            "needs_setup": auth.needs_setup,
            "version": version,
        }

    @router.post("/admin/api/setup")
    async def setup(request: Request) -> JSONResponse:
        if not auth.needs_setup:
            return JSONResponse({"detail": "已经设置过密码"}, status_code=400)
        body = await request.json()
        try:
            auth.setup(str(body.get("password", "")))
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        token = auth.login(str(body.get("password")))
        response = JSONResponse({"ok": True})
        response.set_cookie(COOKIE_NAME, token or "", httponly=True, samesite="strict", max_age=SESSION_TTL)
        return response

    @router.post("/admin/api/login")
    async def login(request: Request) -> JSONResponse:
        body = await request.json()
        token = auth.login(str(body.get("password", "")))
        if token is None:
            return JSONResponse({"detail": "密码不对"}, status_code=401)
        response = JSONResponse({"ok": True})
        response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="strict", max_age=SESSION_TTL)
        return response

    @router.post("/admin/api/logout")
    async def logout() -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE_NAME)
        return response

    @router.get("/admin/api/status")
    async def status(request: Request) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        return {
            "version": version,
            "upstream": settings.upstream_url,
            "native_mode": settings.native_mode,
            "native_enabled": runtime.options.native_enabled,
            "progress_records": store.count(),
            "stats": proxy.stats,
            "recent": store.recent(10),
        }

    @router.get("/admin/api/settings")
    async def get_settings(request: Request) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        options = runtime.options
        return {
            "native_enabled": options.native_enabled,
            "played_threshold": options.played_threshold,
            "native_min_interval": options.native_min_interval,
            "sync_grace_seconds": options.sync_grace_seconds,
            "sync_stream_prefs": options.sync_stream_prefs,
            "log_level": options.log_level,
        }

    @router.post("/admin/api/settings")
    async def save_settings(request: Request) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        body = await request.json()
        try:
            options = runtime.update(**body)
        except (TypeError, ValueError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        return {"ok": True, "options": options.__dict__}

    @router.post("/admin/api/settings/reset")
    async def reset_settings(request: Request) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        options = runtime.reset()
        return {"ok": True, "options": options.__dict__}

    @router.get("/admin/api/skips/{collection_id}")
    async def skips(request: Request, collection_id: str) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        writer = getattr(proxy, "writer", None)
        ranges = writer.list_skips(collection_id) if writer is not None else []
        return {"collection_id": collection_id, "skips": ranges}

    @router.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> PlainTextResponse:
        stats = proxy.stats
        lines = [
            "# HELP bridge_progress_total 收到的进度上报数",
            "# TYPE bridge_progress_total counter",
            f"bridge_progress_total {stats.get('progress', 0)}",
            "# HELP bridge_native_written_total 写库成功次数",
            "# TYPE bridge_native_written_total counter",
            f"bridge_native_written_total {stats.get('native_written', 0)}",
            "# HELP bridge_native_failed_total 写库失败次数",
            "# TYPE bridge_native_failed_total counter",
            f"bridge_native_failed_total {stats.get('native_failed', 0)}",
            "# HELP bridge_played_total 已看回写次数",
            "# TYPE bridge_played_total counter",
            f"bridge_played_total {stats.get('played', 0)}",
            "# HELP bridge_progress_records 本地进度记录数",
            "# TYPE bridge_progress_records gauge",
            f"bridge_progress_records {store.count()}",
        ]
        return PlainTextResponse("\n".join(lines) + "\n")

    return router

