"""接口行为：透传保真、流式、观测、健康检查。"""
from __future__ import annotations

import logging

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
    assert body["UserData"]["PlaybackPositionTicks"] == 500000000


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
