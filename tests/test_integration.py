"""接口行为：透传保真、流式、观测、健康检查。"""
from __future__ import annotations

import logging
import time

import httpx
import pytest


def test_healthz(client: httpx.Client) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "upstream" in body


def test_upstream_401_passes_through(client: httpx.Client) -> None:
    r = client.get("/Users/Me", headers={"X-Emby-Token": "t0ken"})
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}
    assert r.headers["x-reason"] == "no-token"


def test_upstream_404_passes_through(client: httpx.Client) -> None:
    r = client.get("/Users/u1/Items/i1/UserData")
    assert r.status_code == 404


def test_unknown_path_passes_through(client: httpx.Client) -> None:
    r = client.get("/Something/Else")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "path": "/Something/Else"}


def test_range_request_returns_206_with_content_range(client: httpx.Client) -> None:
    r = client.get("/Videos/v1/stream", headers={"Range": "bytes=4-9"})
    assert r.status_code == 206
    assert r.headers["content-range"] == "bytes 4-9/16"
    assert r.content == b"456789"


def test_head_request_returns_headers_without_body(client: httpx.Client) -> None:
    r = client.head("/Videos/v1/stream")
    assert r.status_code == 200
    assert r.content == b""


def test_gzip_response_is_readable(client: httpx.Client) -> None:
    r = client.get("/Gzip/Json", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.json() == {"ServerName": "极影视"}


def test_chunked_response_passes_through(client: httpx.Client) -> None:
    r = client.get("/Chunked/Stream")
    assert r.status_code == 200
    assert r.content == b"aaabbbccc"


def test_progress_post_recorded_and_redacted(client: httpx.Client) -> None:
    token = "super-secret-token"
    body = {"ItemId": "i1", "PositionTicks": 6000000000, "PlaySessionId": "ps-1"}
    r = client.post(
        "/Sessions/Playing/Progress",
        json=body,
        headers={"X-Emby-Token": token, "Authorization": f"MediaBrowser Token={token}"},
    )
    assert r.status_code == 204

    recent = client.get("/debug/recent", params={"n": 5})
    assert recent.status_code == 200
    entries = recent.json()["events"]
    assert entries, "进度上报必须出现在 /debug/recent 里"
    first = entries[0]
    assert first["path"] == "/Sessions/Playing/Progress"
    assert first["item_id"] == "i1"
    assert first["position_ticks"] == 6000000000
    assert first["has_position_ticks"] is True
    assert token not in recent.text


def test_token_not_in_logs(client: httpx.Client, caplog: pytest.LogCaptureFixture) -> None:
    token = "another-secret-token"
    body = {"ItemId": "i1", "PositionTicks": 10000000}
    client.post("/Sessions/Playing/Progress", json=body, headers={"X-Emby-Token": token})
    with caplog.at_level(logging.DEBUG):
        client.get("/Users/Me", headers={"X-Emby-Token": token})
    assert token not in caplog.text


def test_dead_upstream_returns_502(upstream: object, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import Settings
    from app.main import create_app
    from tests.conftest import LiveServer, free_port

    settings = Settings(
        upstream_url="http://127.0.0.1:1",
        listen_port=8022,
        db_path=":memory:",
        log_level="INFO",
        tz="Asia/Shanghai",
        played_threshold=0.9,
    )
    with LiveServer(create_app(settings), free_port()) as server:
        r = httpx.get(f"{server.url}/System/Info/Public", timeout=10, trust_env=False)
    assert r.status_code == 502
    assert "upstream" in r.json()["error"].lower()


def test_response_carries_single_date_header(client: httpx.Client) -> None:
    r = client.get("/Users/Me")
    # 上游的 date 不能让星舰再加一条，重复 Date 是非法响应
    assert len(r.headers.get_list("date")) == 1


def test_api_key_in_query_never_logged(client: httpx.Client, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        r = client.get("/Users/Me?api_key=QUERY-SECRET-VALUE")
    assert r.status_code == 401
    assert "QUERY-SECRET-VALUE" not in caplog.text


def test_emby_prefixed_progress_recorded_even_if_upstream_rejects(client: httpx.Client) -> None:
    body = {"ItemId": "i9", "PositionTicks": 6000000000, "PlaySessionId": "ps-9"}
    r = client.post(
        "/emby/Sessions/Playing/Progress",
        json=body,
        headers={"X-Emby-Token": "emby-token-value", "Content-Type": "application/json"},
    )
    assert r.status_code == 400  # 上游 400 必须原样回传，不伪造成功
    entry = client.get("/debug/recent", params={"n": 1}).json()["events"][0]
    assert entry["path"] == "/emby/Sessions/Playing/Progress"
    assert entry["position_ticks"] == 6000000000
    assert entry["has_position_ticks"] is True
    assert "emby-token-value" not in str(entry)


def test_item_detail_gets_local_progress(client: httpx.Client) -> None:
    token = "resume-token"
    client.post(
        "/emby/Sessions/Playing/Progress",
        json={"ItemId": "i1", "PositionTicks": 6000000000},
        headers={"X-Emby-Token": token},
    )
    body = client.get("/emby/Users/u1/Items/i1", headers={"X-Emby-Token": token}).json()
    assert body["UserData"]["PlaybackPositionTicks"] == 6000000000
    assert body["UserData"]["PlayedPercentage"] == 10.0
    assert body["RunTimeTicks"] == 60000000000  # 非 UserData 字段不被破坏


def test_upstream_newer_progress_wins(client: httpx.Client) -> None:
    token = "resume-token-2"
    client.post(
        "/emby/Sessions/Playing/Progress",
        json={"ItemId": "i2", "PositionTicks": 6000000000},
        headers={"X-Emby-Token": token},
    )
    body = client.get("/emby/Users/u1/Items/i2", headers={"X-Emby-Token": token}).json()
    assert body["UserData"]["PlaybackPositionTicks"] == 12000000000


def test_progress_isolated_per_token(client: httpx.Client) -> None:
    client.post(
        "/emby/Sessions/Playing/Progress",
        json={"ItemId": "i1", "PositionTicks": 6000000000},
        headers={"X-Emby-Token": "user-a"},
    )
    body = client.get("/emby/Users/u1/Items/i1", headers={"X-Emby-Token": "user-b"}).json()
    assert body["UserData"]["PlaybackPositionTicks"] == 0  # 另一个 token 看不到 user-a 的进度


def test_token_in_query_variant_supported(client: httpx.Client) -> None:
    """Hills 实测把 token 放 query，不放 header：写和读都要认。"""
    query = {"X-Emby-Token": "query-token"}
    client.post(
        "/emby/Sessions/Playing/Progress",
        params=query,
        json={"ItemId": "i1", "PositionTicks": 6000000000},
    )
    body = client.get("/emby/Users/u1/Items/i1", params=query).json()
    assert body["UserData"]["PlaybackPositionTicks"] == 6000000000


def test_resume_list_rewritten(client: httpx.Client) -> None:
    token = "resume-list-token"
    client.post(
        "/emby/Sessions/Playing/Progress?UserId=u1",
        json={"ItemId": "i1", "PositionTicks": 6000000000},
        headers={"X-Emby-Token": token},
    )
    body = client.get("/emby/Users/u1/Items/Resume", headers={"X-Emby-Token": token}).json()
    assert body["Items"][0]["UserData"]["PlaybackPositionTicks"] == 6000000000
    assert body["TotalRecordCount"] == 1


def test_played_write_back_at_threshold(client: httpx.Client, upstream) -> None:
    token = "played-token"
    # 先读一次条目，缓存 RunTimeTicks（6000 秒）
    client.get("/emby/Users/u1/Items/i1", headers={"X-Emby-Token": token})
    response = client.post(
        "/emby/Sessions/Playing/Progress?UserId=u1",
        json={"ItemId": "i1", "PositionTicks": 57_000_000_000},
        headers={"X-Emby-Token": token},
    )
    assert response.status_code == 400  # 上游拒绝也原样回传
    assert _wait_for_upstream(upstream, "played-items")
    body = client.get("/emby/Users/u1/Items/i1", headers={"X-Emby-Token": token}).json()
    assert body["UserData"]["Played"] is True


def test_no_write_back_below_threshold(client: httpx.Client, upstream) -> None:
    token = "below-token"
    client.get("/emby/Users/u1/Items/i1", headers={"X-Emby-Token": token})
    client.post(
        "/emby/Sessions/Playing/Progress?UserId=u1",
        json={"ItemId": "i1", "PositionTicks": 30_000_000_000},
        headers={"X-Emby-Token": token},
    )
    time.sleep(0.4)
    assert not any(call["path"] == "played-items" for call in upstream.seen["calls"])


def _wait_for_upstream(upstream, marker: str, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(call["path"] == marker for call in upstream.seen["calls"]):
            return True
        time.sleep(0.05)
    return False


def test_played_write_back_stops_when_upstream_confirms(client: httpx.Client, upstream) -> None:
    token = "confirmed-token"
    client.get("/emby/Users/u1/Items/i1", headers={"X-Emby-Token": token})
    client.post(
        "/emby/Sessions/Playing/Progress?UserId=u1",
        json={"ItemId": "i1", "PositionTicks": 57_000_000_000},
        headers={"X-Emby-Token": token},
    )
    assert _wait_for_upstream(upstream, "played-items")
    time.sleep(0.3)
    assert sum(1 for call in upstream.seen["calls"] if call["path"] == "played-items") == 1


def test_played_write_back_falls_back_when_upstream_ignores(client: httpx.Client, upstream) -> None:
    """真实极影视对 POST 返回 200 却不改状态：必须验证，再换不带 /emby 的写法。"""
    token = "stubborn-token"
    client.get("/emby/Users/u2/Items/i1", headers={"X-Emby-Token": token})
    client.post(
        "/emby/Sessions/Playing/Progress?UserId=u2",
        json={"ItemId": "i1", "PositionTicks": 57_000_000_000},
        headers={"X-Emby-Token": token},
    )
    assert _wait_for_upstream(upstream, "played-u2-plain", timeout=5.0)
    markers = [call["path"] for call in upstream.seen["calls"] if call["path"].startswith("played-u2")]
    assert markers == ["played-u2-prefixed", "played-u2-plain"]


NATIVE_ITEM = "collection_560a79a3e816b6e_484e30ab-18be-4c7a-a6dd-e7105cad7e48"


def test_native_write_updates_playlist_table(tmp_path, upstream) -> None:
    """Hills 上报的位置要落到极影视自己的 zvideo_playlist 表。"""
    import sqlite3

    from app.config import Settings
    from app.main import create_app
    from tests.conftest import LiveServer, free_port

    db_path = tmp_path / "zvideo.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE zvideo_playlist (id INTEGER PRIMARY KEY AUTOINCREMENT, user_name varchar,"
        " classification_id varchar, collection_id varchar, video_id varchar, name varchar, path varchar,"
        " play_duration integer, created_at datetime, updated_at datetime, video_duration integer,"
        " audio_index text, subtitle_index text);"
        "CREATE UNIQUE INDEX user_playlist ON zvideo_playlist (user_name, classification_id, collection_id);"
        "CREATE TABLE zvideo_list (id INTEGER PRIMARY KEY AUTOINCREMENT, user_name varchar, video_id varchar,"
        " collection_id varchar, name varchar, path varchar, duration integer, state tinyint default 1);"
    )
    conn.execute(
        "INSERT INTO zvideo_playlist (user_name, classification_id, collection_id, play_duration, updated_at)"
        " VALUES (?,?,?,?,?)",
        ("17611545258", "484e30ab-18be-4c7a-a6dd-e7105cad7e48", "560a79a3e816b6e", 100, "2026-10-26 12:00:00"),
    )
    conn.commit()
    conn.close()

    settings = Settings(
        upstream_url=upstream.url,
        listen_port=8022,
        db_path=":memory:",
        log_level="INFO",
        tz="Asia/Shanghai",
        played_threshold=0.9,
        native_mode="local",
        native_db_path=str(db_path),
        native_user="17611545258",
        native_min_interval=0.0,
    )
    with LiveServer(create_app(settings), free_port()) as server:
        response = httpx.post(
            f"{server.url}/emby/Sessions/Playing/Progress?UserId=u1",
            json={"ItemId": NATIVE_ITEM, "PositionTicks": 18_000_000_000},
            headers={"X-Emby-Token": "native-token"},
            timeout=10,
            trust_env=False,
        )
        assert response.status_code == 400  # 上游拒绝，原生写入照旧
        position = None
        deadline = time.time() + 5
        while time.time() < deadline:
            row = sqlite3.connect(db_path).execute(
                "SELECT play_duration FROM zvideo_playlist WHERE collection_id = ?", ("560a79a3e816b6e",)
            ).fetchone()
            position = row[0] if row else None
            if position == 1800:
                break
            time.sleep(0.05)
    assert position == 1800
