"""控制台：首次设置、登录、设置读写、指标。"""
from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.main import create_app
from tests.conftest import LiveServer, free_port


def make_client(tmp_path):
    settings = Settings(
        upstream_url="http://127.0.0.1:1",
        listen_port=8022,
        db_path=str(tmp_path / "bridge.db"),
        log_level="INFO",
        tz="Asia/Shanghai",
        played_threshold=0.9,
    )
    server = LiveServer(create_app(settings), free_port())
    client = httpx.Client(base_url=server.url, timeout=10.0, trust_env=False)
    return settings, server, client


def test_first_run_setup_login_and_settings(tmp_path) -> None:
    settings, server, client = make_client(tmp_path)
    with server, client:
        assert client.get("/admin/api/session").json()["needs_setup"] is True
        assert client.get("/admin/api/status").status_code == 401

        setup = client.post(
            "/admin/api/setup",
            json={"password": "secret123"},
            headers={"X-Requested-With": "fetch"},
        )
        assert setup.status_code == 200
        assert client.get("/admin/api/status").status_code == 200

        saved = client.post(
            "/admin/api/settings",
            json={"played_threshold": 0.75, "native_enabled": False, "log_level": "DEBUG"},
            headers={"X-Requested-With": "fetch"},
        )
        assert saved.status_code == 200
        current = client.get("/admin/api/settings").json()
        assert current["played_threshold"] == 0.75
        assert current["native_enabled"] is False

        # 没有 X-Requested-With 的写操作被拒
        assert client.post("/admin/api/settings", json={"played_threshold": 0.5}).status_code == 400

        client.post("/admin/api/logout", headers={"X-Requested-With": "fetch"})
        assert client.get("/admin/api/status").status_code == 401

        assert client.post(
            "/admin/api/login",
            json={"password": "wrong"},
            headers={"X-Requested-With": "fetch"},
        ).status_code == 401
        assert client.post(
            "/admin/api/login",
            json={"password": "secret123"},
            headers={"X-Requested-With": "fetch"},
        ).status_code == 200


def test_setup_rejects_short_password(tmp_path) -> None:
    _, server, client = make_client(tmp_path)
    with server, client:
        response = client.post("/admin/api/setup", json={"password": "123"}, headers={"X-Requested-With": "fetch"})
        assert response.status_code == 400
        assert client.get("/admin/api/session").json()["needs_setup"] is True


def test_admin_page_served(tmp_path) -> None:
    _, server, client = make_client(tmp_path)
    with server, client:
        page = client.get("/admin")
        assert page.status_code == 200
        assert "极影视进度桥" in page.text


def test_metrics_exposes_counters(tmp_path) -> None:
    _, server, client = make_client(tmp_path)
    with server, client:
        text = client.get("/metrics").text
        assert "bridge_progress_total" in text
        assert "bridge_native_written_total" in text
        assert "bridge_progress_records" in text


def test_icon_and_reset(tmp_path) -> None:
    _, server, client = make_client(tmp_path)
    with server, client:
        icon = client.get("/icon.png")
        assert icon.status_code == 200
        assert icon.headers["content-type"] == "image/png"
        assert "no-cache" in icon.headers["cache-control"]
        assert client.get("/favicon.ico").status_code == 200

        # 换图标后必须能立刻拿到新图：HEAD 可用，且页面里的 URL 带内容哈希
        assert client.head("/icon.png").status_code == 200
        page = client.get("/admin").text
        assert "?v=" in page
        assert "no-cache" in client.get("/admin").headers["cache-control"]
        assert "__ICON_V__" not in page

        client.post("/admin/api/setup", json={"password": "secret123"}, headers={"X-Requested-With": "fetch"})
        client.post(
            "/admin/api/settings",
            json={"played_threshold": 0.55},
            headers={"X-Requested-With": "fetch"},
        )
        assert client.get("/admin/api/settings").json()["played_threshold"] == pytest.approx(0.55)
        reset = client.post("/admin/api/settings/reset", headers={"X-Requested-With": "fetch"})
        assert reset.status_code == 200
        assert client.get("/admin/api/settings").json()["played_threshold"] == pytest.approx(0.9)


def test_settings_survive_restart(tmp_path) -> None:
    settings, server, client = make_client(tmp_path)
    with server, client:
        client.post("/admin/api/setup", json={"password": "secret123"}, headers={"X-Requested-With": "fetch"})
        client.post(
            "/admin/api/settings",
            json={"played_threshold": 0.6},
            headers={"X-Requested-With": "fetch"},
        )
    # 重新装配应用（同一个 db 文件）
    with LiveServer(create_app(settings), free_port()) as server2, httpx.Client(
        base_url=server2.url, timeout=10.0, trust_env=False
    ) as client2:
        assert client2.get("/admin/api/session").json()["needs_setup"] is False
        assert client2.post(
            "/admin/api/login", json={"password": "secret123"}, headers={"X-Requested-With": "fetch"}
        ).status_code == 200
        assert client2.get("/admin/api/settings").json()["played_threshold"] == pytest.approx(0.6)
