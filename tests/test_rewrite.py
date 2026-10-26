"""时间解析、路径判定与「极影视为准」的合并策略。"""
from __future__ import annotations

import pytest

from app.rewrite import (
    LocalProgress,
    collect_runtimes,
    is_rewritable_path,
    merge_user_data,
    parse_iso8601,
    rewrite_payload,
)

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


def test_upstream_record_always_wins() -> None:
    item = {
        "Id": "i1",
        "RunTimeTicks": 60000000000,
        "UserData": {"PlaybackPositionTicks": 500000000, "LastPlayedDate": "2026-10-26T05:00:00Z"},
    }
    merged, cleared = merge_user_data(item, LocalProgress(6000000000, UTC_EPOCH), now=UTC_EPOCH + 3600)
    assert merged["UserData"]["PlaybackPositionTicks"] == 500000000
    assert cleared is False


def test_upstream_played_wins() -> None:
    item = {"Id": "i1", "UserData": {"Played": True, "PlaybackPositionTicks": 0}}
    merged, cleared = merge_user_data(item, LocalProgress(6000000000, UTC_EPOCH), now=UTC_EPOCH + 3600)
    assert merged["UserData"]["Played"] is True
    assert merged["UserData"]["PlaybackPositionTicks"] == 0
    assert cleared is False


def test_recent_local_fills_empty_upstream_with_grace() -> None:
    item = {"Id": "i1", "RunTimeTicks": 60000000000, "UserData": {"PlaybackPositionTicks": 0}}
    merged, cleared = merge_user_data(item, LocalProgress(6000000000, UTC_EPOCH), now=UTC_EPOCH + 5)
    assert merged["UserData"]["PlaybackPositionTicks"] == 6000000000
    assert merged["UserData"]["PlayedPercentage"] == pytest.approx(10.0)
    assert cleared is False
    assert item["UserData"]["PlaybackPositionTicks"] == 0  # 入参不被改


def test_stale_local_with_empty_upstream_is_cleared() -> None:
    """用户在极影视里删了观看记录：本地旧记录必须跟着清掉。"""
    item = {"Id": "i1", "RunTimeTicks": 60000000000, "UserData": {"PlaybackPositionTicks": 0}}
    merged, cleared = merge_user_data(item, LocalProgress(6000000000, UTC_EPOCH), now=UTC_EPOCH + 60)
    assert cleared is True
    assert merged == item


def test_merge_without_local_returns_equivalent_item() -> None:
    item = {"Id": "i1", "UserData": {"PlaybackPositionTicks": 42}}
    merged, cleared = merge_user_data(item, None)
    assert merged == item
    assert cleared is False


def test_rewrite_walks_lists_and_keeps_other_fields() -> None:
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
    cleared: list[str] = []
    out = rewrite_payload(
        payload,
        lambda item_id: local if item_id == "i1" else None,
        now=UTC_EPOCH + 5,
        on_clear=cleared.append,
    )
    assert out["Items"][0]["UserData"]["PlaybackPositionTicks"] == 7000000000
    assert out["Items"][1] == {"Id": "i2", "Name": "没有 UserData"}
    assert out["Items"][2]["UserData"]["PlaybackPositionTicks"] == 0
    assert out["TotalRecordCount"] == 3
    assert out["ServerName"] == "极影视"
    assert cleared == []


def test_rewrite_reports_cleared_items() -> None:
    payload = {"Items": [{"Id": "i1", "UserData": {"PlaybackPositionTicks": 0}}]}
    local = LocalProgress(position_ticks=7000000000, updated_at=UTC_EPOCH)
    cleared: list[str] = []
    rewrite_payload(payload, lambda _: local, now=UTC_EPOCH + 60, on_clear=cleared.append)
    assert cleared == ["i1"]


def test_collect_runtimes_walks_nested_payload() -> None:
    payload = {
        "Items": [
            {"Id": "i1", "RunTimeTicks": 60000000000},
            {"Id": "i2", "UserData": {"ItemId": "i1"}},
        ],
        "Id": "parent",
        "RunTimeTicks": 10000000,
    }
    assert collect_runtimes(payload) == {"i1": 60000000000, "parent": 10000000}


def test_path_gate() -> None:
    assert is_rewritable_path("/emby/Users/u1/Items/i1") is True
    assert is_rewritable_path("/Users/u1/Items/i1") is True
    assert is_rewritable_path("/emby/Users/Me/Items/i1") is True
    assert is_rewritable_path("/emby/Users/u1/Items") is True
    assert is_rewritable_path("/emby/Users/u1/Items/Resume") is True
    assert is_rewritable_path("/emby/Users/u1/Items/Latest") is True
    assert is_rewritable_path("/emby/Users/Me/Items/Resume") is True
    assert is_rewritable_path("/Videos/v1/stream.mkv") is False
    assert is_rewritable_path("/emby/Items/i1/PlaybackInfo") is False
    assert is_rewritable_path("/emby/Items/i1/Images/Primary") is False
