"""脱敏工具的行为：日志里不允许出现任何 token。"""
from __future__ import annotations

from app.redact import redact_headers, redact_json, redact_url

TOKEN = "s3cr3t-token-value"


def test_redact_headers_masks_token_case_insensitively() -> None:
    out = redact_headers({"X-Emby-Token": TOKEN, "Authorization": f"MediaBrowser Token={TOKEN}", "Accept": "application/json"})
    assert TOKEN not in str(out)
    assert out["Accept"] == "application/json"
    assert out["X-Emby-Token"] == "***"


def test_redact_headers_keeps_header_names() -> None:
    out = redact_headers({"authorization": "Bearer abc"})
    assert set(out) == {"authorization"}


def test_redact_json_masks_nested_keys_without_mutating_input() -> None:
    body = {"api_key": TOKEN, "nested": {"items": [{"token": TOKEN}, {"Name": "第 1 集"}]}}
    out = redact_json(body)
    assert TOKEN not in str(out)
    assert body["api_key"] == TOKEN  # 原对象不能被改
    assert out["nested"]["items"][1]["Name"] == "第 1 集"


def test_redact_json_keeps_scalars_and_lists() -> None:
    assert redact_json({"PositionTicks": 6000000000}) == {"PositionTicks": 6000000000}
    assert redact_json([1, "a", None]) == [1, "a", None]


def test_redact_url_masks_query_credentials() -> None:
    out = redact_url(f"http://h:8021/Users/Me?api_key={TOKEN}&a=1")
    assert TOKEN not in out
    assert "a=1" in out


def test_redact_url_masks_emby_token_query_key() -> None:
    # Hills 实测会把 X-Emby-Token 塞进 query，键名和 api_key 一样属于凭据
    out = redact_url("http://h/emby/Users/Me?X-Emby-Token=deadbeefcafe&UserId=u1")
    assert "deadbeefcafe" not in out
    assert "UserId=u1" in out


def test_redact_json_masks_emby_token_and_authorization() -> None:
    out = redact_json({"X-Emby-Token": TOKEN, "X-Emby-Authorization": f"Emby Token={TOKEN}"})
    assert TOKEN not in str(out)
