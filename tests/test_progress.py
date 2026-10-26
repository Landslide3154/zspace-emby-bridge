"""进度上报解析：M0 的结论就来自这里，字段判定必须明确。"""
from __future__ import annotations

import json

from app.proxy import parse_progress_event


def test_json_body_with_position() -> None:
    body = json.dumps({"ItemId": "i1", "PositionTicks": 6000000000, "PlaySessionId": "s1"}).encode()
    event = parse_progress_event("POST", "/Sessions/Playing/Progress", "", body)
    assert event is not None
    assert event.item_id == "i1"
    assert event.position_ticks == 6000000000
    assert event.play_session_id == "s1"
    assert event.has_position_ticks is True
    assert event.body_format == "json"


def test_position_zero_counts_as_present() -> None:
    event = parse_progress_event(
        "POST", "/Sessions/Playing/Progress", "", json.dumps({"ItemId": "i1", "PositionTicks": 0}).encode()
    )
    assert event is not None
    assert event.has_position_ticks is True
    assert event.position_ticks == 0


def test_missing_position_still_recorded() -> None:
    event = parse_progress_event("POST", "/Sessions/Playing/Stopped", "", b'{"ItemId":"i1"}')
    assert event is not None
    assert event.has_position_ticks is False
    assert event.position_ticks is None


def test_query_string_body_supported() -> None:
    event = parse_progress_event("POST", "/Sessions/Playing/Progress", "ItemId=i2&PositionTicks=123", b"")
    assert event is not None
    assert event.item_id == "i2"
    assert event.position_ticks == 123
    assert event.body_format == "query"


def test_non_control_path_ignored() -> None:
    assert parse_progress_event("GET", "/Users/Me", "", b"") is None


def test_get_on_control_path_ignored() -> None:
    assert parse_progress_event("GET", "/Sessions/Playing/Progress", "", b"") is None


def test_control_path_is_case_and_slash_tolerant() -> None:
    event = parse_progress_event("POST", "/sessions/playing/", "", b"{}")
    assert event is not None
    assert event.has_position_ticks is False
    assert event.body_format in {"json", "empty"}


def test_emby_prefixed_control_path_recognized() -> None:
    # Hills 实测走 /emby/Sessions/Playing/Progress，不带前缀会漏记
    body = json.dumps({"ItemId": "i9", "PositionTicks": 6000000000}).encode()
    event = parse_progress_event("POST", "/emby/Sessions/Playing/Progress", "", body)
    assert event is not None
    assert event.item_id == "i9"
    assert event.position_ticks == 6000000000
    assert event.path == "/emby/Sessions/Playing/Progress"


def test_body_summary_keeps_ticks_for_evidence() -> None:
    body = json.dumps({"ItemId": "i1", "PositionTicks": 6000000000, "api_key": "leak-me"}).encode()
    event = parse_progress_event("POST", "/emby/Sessions/Playing/Progress", "", body)
    assert event is not None
    assert "6000000000" in event.body_summary
    assert "leak-me" not in event.body_summary
