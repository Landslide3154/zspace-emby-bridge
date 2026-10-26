"""时间解析与合并策略：只在本地更新时才覆盖极影视的值。"""
from __future__ import annotations

import pytest

from app.rewrite import LocalProgress, is_rewritable_path, merge_user_data, parse_iso8601, rewrite_payload

# 2026-10-26T05:15:25Z
UTC_EPOCH = 1792991725.0


def test_parse_iso8601_variants() -> None:
    assert parse_iso8601("2026-10-26T05:15:25Z") is not None
    assert parse_iso8601("2026-10-26T05:15:25.0310000Z") is not None
    assert parse_iso8601("2026-10-26T13:15:25+08:00") == parse_iso8601("2026-10-26T05:15:25Z")
    assert parse_iso8601("2026-10-26T05:15:25") == parse_iso8601("2026-10-26T05:15:25Z")
    assert parse_iso8601("not-a-date") is None
    assert parse_iso8601(None) is None
    assert parse_iso8601("") is None


def test_local_newer_overrides_position_and_percentage() -> None:
    item = {
        "Id": "i1",
        "RunTimeTicks": 60000000000,  # 100 分钟
        "UserData": {"PlaybackPositionTicks": 500000000, "LastPlayedDate": "2026-10-26T05:00:00Z"},
    }
    local = LocalProgress(position_ticks=6000000000, updated_at=UTC_EPOCH)
    merged = merge_user_data(item, local)
    assert merged["UserData"]["PlaybackPositionTicks"] == 6000000000
    assert merged["UserData"]["PlayedPercentage"] == pytest.approx(10.0)
    assert item["UserData"]["PlaybackPositionTicks"] == 500000000  # 入参不被改


def test_upstream_newer_wins() -> None:
    item = {
        "Id": "i1",
        "RunTimeTicks": 60000000000,
        "UserData": {"PlaybackPositionTicks": 12000000000, "LastPlayedDate": "2026-10-26T06:00:00Z"},
    }
    local = LocalProgress(position_ticks=6000000000, updated_at=UTC_EPOCH)
    merged = merge_user_data(item, local)
    assert merged["UserData"]["PlaybackPositionTicks"] == 12000000000


def test_local_wins_when_upstream_has_no_last_played() -> None:
    item = {"Id": "i1", "UserData": {"PlaybackPositionTicks": 0}}
    merged = merge_user_data(item, LocalProgress(position_ticks=1230000000, updated_at=UTC_EPOCH))
    assert merged["UserData"]["PlaybackPositionTicks"] == 1230000000


def test_merge_without_local_returns_equivalent_item() -> None:
    item = {"Id": "i1", "UserData": {"PlaybackPositionTicks": 42}}
    assert merge_user_data(item, None) == item


def test_rewrite_walks_lists_and_ignores_foreign_fields() -> None:
    payload = {
        "Items": [
            {"Id": "i1", "UserData": {"PlaybackPositionTicks": 0}},
            {"Id": "i2", "Name": "没有 UserData"},
            {"Id": "i3", "UserData": {"PlaybackPositionTicks": 0}},
        ],
        "TotalRecordCount": 3,
        "ServerName": "极影视",
    }
    local = LocalProgress(position_ticks=7000000000, updated_at=UTC_EPOCH)
    out = rewrite_payload(payload, _resolver({"i1": local, "i3": None}))
    assert out["Items"][0]["UserData"]["PlaybackPositionTicks"] == 7000000000
    assert out["Items"][1] == {"Id": "i2", "Name": "没有 UserData"}
    assert out["Items"][2]["UserData"]["PlaybackPositionTicks"] == 0
    assert out["TotalRecordCount"] == 3
    assert out["ServerName"] == "极影视"


def _resolver(mapping: dict):
    return lambda item_id: mapping.get(item_id)


def test_path_gate() -> None:
    assert is_rewritable_path("/emby/Users/u1/Items/i1") is True
    assert is_rewritable_path("/Users/u1/Items/i1") is True
    assert is_rewritable_path("/emby/Users/Me/Items/i1") is True
    assert is_rewritable_path("/emby/Users/u1/Items/Resume") is False  # M2
    assert is_rewritable_path("/Videos/v1/stream.mkv") is False
    assert is_rewritable_path("/emby/Items/i1/PlaybackInfo") is False
