"""控制台新增能力：片名/搜索、上游测试、密码修改、白名单、限流、导出。"""
from __future__ import annotations

import sqlite3

import httpx

from app.config import Settings
from app.main import create_app
from tests.conftest import LiveServer, free_port

USER = "17611545258"
COLLECTION = "560a79a3e816b6e"
CLASSIFICATION = "484e30ab-18be-4c7a-a6dd-e7105cad7e48"
ITEM = f"collection_{COLLECTION}_{CLASSIFICATION}"

ZVIDEO_SCHEMA = """
CREATE TABLE zvideo_playlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_name varchar, classification_id varchar,
    collection_id varchar, video_id varchar, name varchar, path varchar, play_duration integer,
    created_at datetime, updated_at datetime, video_duration integer, audio_index text, subtitle_index text);
CREATE UNIQUE INDEX user_playlist ON zvideo_playlist (user_name, classification_id, collection_id);
CREATE TABLE zvideo_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_name varchar, video_id varchar, collection_id varchar,
    name varchar, path varchar, duration integer, state tinyint default 1);
CREATE TABLE zvideo_collection (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_name varchar, collection_id varchar, title varchar, updated integer default 0);
CREATE TABLE zvideo_skip (collection_id varchar, start_time integer, end_time integer);
"""


def make_zvideo_db(path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(ZVIDEO_SCHEMA)
    conn.execute(
        "INSERT INTO zvideo_collection (user_name, collection_id, title, updated) VALUES (?,?,?,?)",
        (USER, COLLECTION, "后室", 100),
    )
    conn.execute(
        "INSERT INTO zvideo_list (user_name, video_id, collection_id, name, path, duration, state)"
        " VALUES (?,?,?,?,?,?,?)",
        (USER, "7d2002151cff985", COLLECTION, "后室 (2026) - 2160p.mkv", "/media/a.mkv", 6636, 1),
    )
    conn.execute("INSERT INTO zvideo_skip (collection_id, start_time, end_time) VALUES (?,?,?)", (COLLECTION, 12, 95))
    conn.commit()
    conn.close()


def start(tmp_path):
    zv = tmp_path / "zvideo.db"
    make_zvideo_db(zv)
    settings = Settings(
        upstream_url="http://127.0.0.1:1",
        listen_port=8022,
        db_path=str(tmp_path / "bridge.db"),
        log_level="INFO",
        tz="Asia/Shanghai",
        played_threshold=0.9,
        native_mode="local",
        native_db_path=str(zv),
        native_user=USER,
    )
    server = LiveServer(create_app(settings), free_port())
    client = httpx.Client(base_url=server.url, timeout=10.0, trust_env=False)
    return server, client


def login(client) -> None:
    client.post("/admin/api/setup", json={"password": "secret123"}, headers={"X-Requested-With": "fetch"})


def test_recent_shows_title_and_file(tmp_path) -> None:
    server, client = start(tmp_path)
    with server, client:
        login(client)
        client.post(
            "/emby/Sessions/Playing/Progress?UserId=u1",
            json={"ItemId": ITEM, "PositionTicks": 60_000_000_000},
            headers={"X-Emby-Token": "t"},
        )
        status = client.get("/admin/api/status").json()
        assert status["recent"], "应有进度记录"
        entry = status["recent"][0]
        assert entry["title"] == "后室"
        assert entry["file"].startswith("后室 (2026)")


def test_search_by_title_returns_skips(tmp_path) -> None:
    server, client = start(tmp_path)
    with server, client:
        login(client)
        data = client.get("/admin/api/skips", params={"q": "后室"}).json()
        assert data["matches"], "按片名应能搜到"
        assert data["matches"][0]["collection_id"] == COLLECTION
        assert data["matches"][0]["skips"] == [{"start": 12, "end": 95}]


def test_search_by_collection_id(tmp_path) -> None:
    server, client = start(tmp_path)
    with server, client:
        login(client)
        data = client.get("/admin/api/search", params={"q": COLLECTION}).json()
        assert data["matches"][0]["title"] == "后室"


def test_upstream_url_change_applies(tmp_path) -> None:
    server, client = start(tmp_path)
    with server, client:
        login(client)
        response = client.post(
            "/admin/api/settings",
            json={"upstream_url": "http://127.0.0.1:9/"},
            headers={"X-Requested-With": "fetch"},
        )
        assert response.status_code == 200
        status = client.get("/admin/api/status").json()
        assert status["upstream"] == "http://127.0.0.1:9"
        test_result = client.post("/admin/api/upstream/test", headers={"X-Requested-With": "fetch"}).json()
        assert test_result["ok"] is False


def test_password_change(tmp_path) -> None:
    server, client = start(tmp_path)
    with server, client:
        login(client)
        bad = client.post(
            "/admin/api/password", json={"old": "nope", "new": "newpass1"}, headers={"X-Requested-With": "fetch"}
        )
        assert bad.status_code == 400
        good = client.post(
            "/admin/api/password", json={"old": "secret123", "new": "newpass1"}, headers={"X-Requested-With": "fetch"}
        )
        assert good.status_code == 200
        client.post("/admin/api/logout", headers={"X-Requested-With": "fetch"})
        assert client.post(
            "/admin/api/login", json={"password": "secret123"}, headers={"X-Requested-With": "fetch"}
        ).status_code == 401
        assert client.post(
            "/admin/api/login", json={"password": "newpass1"}, headers={"X-Requested-With": "fetch"}
        ).status_code == 200


def test_ip_allowlist_blocks_others(tmp_path) -> None:
    server, client = start(tmp_path)
    with server, client:
        login(client)
        app = server._server.config.app  # 拿到同一个应用实例改运行时设置
        app.state.runtime.update(allowed_ips="10.9.9.9")
        assert client.get("/admin/api/status").status_code == 403
        app.state.runtime.update(allowed_ips="")
        assert client.get("/admin/api/status").status_code == 200


def test_login_rate_limited(tmp_path) -> None:
    server, client = start(tmp_path)
    with server, client:
        login(client)
        client.post("/admin/api/logout", headers={"X-Requested-With": "fetch"})
        for _ in range(5):
            client.post("/admin/api/login", json={"password": "bad"}, headers={"X-Requested-With": "fetch"})
        blocked = client.post("/admin/api/login", json={"password": "bad"}, headers={"X-Requested-With": "fetch"})
        assert blocked.status_code == 429


def test_export_contains_settings(tmp_path) -> None:
    server, client = start(tmp_path)
    with server, client:
        login(client)
        text = client.get("/admin/api/export").text
        assert "UPSTREAM_URL=" in text
        assert f"NATIVE_USER={USER}" in text
