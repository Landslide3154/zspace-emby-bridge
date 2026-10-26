"""控制台：首次设置密码、登录、设置、搜索、事件、指标。"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

from .config import Settings
from .runtime import RuntimeConfig
from .store import ProgressStore
from .web_ui import ADMIN_HTML

ASSETS = Path(__file__).parent / "assets"
# 图标 URL 带内容哈希：换图标后浏览器不会再拿旧缓存
ICON_V = hashlib.sha256((ASSETS / "icon-256.png").read_bytes()).hexdigest()[:10]
ADMIN_PAGE = ADMIN_HTML.replace("__ICON_V__", ICON_V)
NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}
COOKIE_NAME = "bridge_admin"
SESSION_TTL = 7 * 24 * 3600
PASSWORD_KEY = "admin_password"
SECRET_KEY = "admin_secret"
MIN_PASSWORD = 6
MAX_FAILURES = 5
FAILURE_WINDOW = 600


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

    def change_password(self, old: str, new: str) -> None:
        if not verify_password(self._password, old):
            raise ValueError("原密码不对")
        self.setup(new)

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
    failures: dict[str, list[float]] = {}

    def client_ip(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def allowlisted(request: Request) -> bool:
        raw = runtime.options.allowed_ips.strip()
        if not raw:
            return True
        allowed = {item.strip() for item in raw.replace(";", ",").split(",") if item.strip()}
        return client_ip(request) in allowed

    def authenticated(request: Request) -> bool:
        return auth.check(request.cookies.get(COOKIE_NAME))

    def guard(request: Request) -> JSONResponse | None:
        if not allowlisted(request):
            return JSONResponse({"detail": "该 IP 不在白名单里"}, status_code=403)
        if not authenticated(request):
            return JSONResponse({"detail": "请先登录"}, status_code=401)
        if request.method not in {"GET", "HEAD"} and request.headers.get("x-requested-with") != "fetch":
            return JSONResponse({"detail": "缺少 X-Requested-With"}, status_code=400)
        return None

    def writer():
        return getattr(proxy, "writer", None)

    def with_names(records: list[dict]) -> list[dict]:
        lookup = getattr(writer(), "lookup", None)
        names: dict[str, dict] = {}
        if lookup is not None and records:
            try:
                names = lookup([record.get("item_id") or "" for record in records])
            except Exception:  # 名字只用于展示，取不到不算错
                names = {}
        for record in records:
            info = names.get(record.get("item_id") or "") or {}
            record["title"] = info.get("title")
            record["file"] = info.get("file")
        return records

    @router.api_route("/icon.png", methods=["GET", "HEAD"])
    async def icon_png() -> FileResponse:
        return FileResponse(ASSETS / "icon-256.png", media_type="image/png", headers=NO_CACHE)

    @router.api_route("/icon-192.png", methods=["GET", "HEAD"])
    async def icon_192() -> FileResponse:
        return FileResponse(ASSETS / "icon-192.png", media_type="image/png", headers=NO_CACHE)

    @router.api_route("/favicon.ico", methods=["GET", "HEAD"])
    async def favicon() -> FileResponse:
        return FileResponse(ASSETS / "icon-64.png", media_type="image/png", headers=NO_CACHE)

    @router.get("/admin", response_class=HTMLResponse)
    async def admin_page() -> HTMLResponse:
        return HTMLResponse(ADMIN_PAGE, headers=NO_CACHE)

    @router.get("/admin/api/session")
    async def session(request: Request) -> dict:
        return {
            "authenticated": authenticated(request),
            "needs_setup": auth.needs_setup,
            "version": version,
            "allowed": allowlisted(request),
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
        ip = client_ip(request)
        now = time.time()
        attempts = [stamp for stamp in failures.get(ip, []) if now - stamp < FAILURE_WINDOW]
        if len(attempts) >= MAX_FAILURES:
            return JSONResponse({"detail": "尝试次数过多，请 10 分钟后再试"}, status_code=429)
        body = await request.json()
        token = auth.login(str(body.get("password", "")))
        if token is None:
            failures[ip] = attempts + [now]
            return JSONResponse({"detail": "密码不对"}, status_code=401)
        failures.pop(ip, None)
        response = JSONResponse({"ok": True})
        response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="strict", max_age=SESSION_TTL)
        return response

    @router.post("/admin/api/logout")
    async def logout() -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE_NAME)
        return response

    @router.post("/admin/api/password")
    async def change_password(request: Request) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        body = await request.json()
        try:
            auth.change_password(str(body.get("old", "")), str(body.get("new", "")))
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        token = auth.login(str(body.get("new", "")))
        response = JSONResponse({"ok": True})
        response.set_cookie(COOKIE_NAME, token or "", httponly=True, samesite="strict", max_age=SESSION_TTL)
        return response

    @router.get("/admin/api/status")
    async def status(request: Request) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        return {
            "version": version,
            "upstream": runtime.options.upstream_url or settings.upstream_url,
            "native_mode": settings.native_mode,
            "native_enabled": runtime.options.native_enabled,
            "listen_port": settings.listen_port,
            "progress_records": store.count(),
            "stats": proxy.stats,
            "recent": with_names(store.recent(12)),
            "events": store.recent_events(8),
            "sessions": with_names(proxy.sessions_view()),
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
            "upstream_url": options.upstream_url,
            "allowed_ips": options.allowed_ips,
        }

    @router.post("/admin/api/settings")
    async def save_settings(request: Request) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        body = await request.json()
        previous_upstream = runtime.options.upstream_url
        try:
            options = runtime.update(**body)
        except (TypeError, ValueError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        if options.upstream_url != previous_upstream:
            await proxy.set_upstream(options.upstream_url)
        return {"ok": True, "options": options.__dict__}

    @router.post("/admin/api/settings/reset")
    async def reset_settings(request: Request) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        previous = runtime.options.upstream_url
        options = runtime.reset()
        if options.upstream_url != previous:
            await proxy.set_upstream(options.upstream_url)
        return {"ok": True, "options": options.__dict__}

    @router.post("/admin/api/upstream/test")
    async def upstream_test(request: Request) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        return await proxy.test_upstream()

    @router.get("/admin/api/search")
    async def search(request: Request, q: str = "") -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        finder = getattr(writer(), "search", None)
        matches = finder(q, 20) if finder is not None else []
        return {"query": q, "matches": matches}

    @router.get("/admin/api/skips")
    async def skips(request: Request, q: str = "") -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        finder = getattr(writer(), "search", None)
        lister = getattr(writer(), "list_skips", None)
        if finder is None or lister is None:
            return {"query": q, "matches": []}
        matches = finder(q, 10)
        for match in matches:
            match["skips"] = lister(match["collection_id"])
        return {"query": q, "matches": matches}

    @router.get("/admin/api/export", response_class=PlainTextResponse)
    async def export_config(request: Request) -> Any:
        denied = guard(request)
        if denied is not None:
            return denied
        options = runtime.options
        lines = [
            "# 由控制台导出，可贴进 .env",
            f"UPSTREAM_URL={options.upstream_url or settings.upstream_url}",
            f"LISTEN_PORT={settings.listen_port}",
            f"DB_PATH={settings.db_path}",
            f"LOG_LEVEL={options.log_level}",
            f"PLAYED_THRESHOLD={options.played_threshold}",
            f"NATIVE_MODE={settings.native_mode}",
            f"NATIVE_DB_PATH={settings.native_db_path}",
            f"NATIVE_USER={settings.native_user}",
            f"NATIVE_MIN_INTERVAL={options.native_min_interval}",
            f"SYNC_GRACE_SECONDS={options.sync_grace_seconds}",
            f"SYNC_STREAM_PREFS={'true' if options.sync_stream_prefs else 'false'}",
            f"ALLOWED_IPS={options.allowed_ips}",
        ]
        return PlainTextResponse("\n".join(lines) + "\n")

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
