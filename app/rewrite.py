"""UserData 重写与新旧进度合并。"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

# 单条目：/Users/{uid}/Items/{id}；列表：/Users/{uid}/Items[/Resume|/Latest] 或 /Items
_ITEM_PATH = re.compile(r"^/(?:emby/)?users/[^/]+/items/(?P<item>[^/?]+)/?$", re.IGNORECASE)
_LIST_PATH = re.compile(r"^/(?:emby/)?(?:users/[^/]+/)?items(?:/(?:resume|latest))?/?$", re.IGNORECASE)
_RESERVED_ITEMS = frozenset({"resume", "latest", "count"})

_ISO8601 = re.compile(
    r"^(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})[T ](?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2})"
    r"(?:\.(?P<frac>\d+))?(?P<tz>Z|[+-]\d{2}:?\d{2})?$"
)


@dataclass(frozen=True)
class LocalProgress:
    position_ticks: int
    updated_at: float
    played: bool = False


def parse_iso8601(value: Any) -> float | None:
    """容错解析成 UTC epoch：带/不带时区、7 位小数、空格分隔都接受。"""
    if not isinstance(value, str):
        return None
    match = _ISO8601.match(value.strip())
    if match is None:
        return None
    fraction = (match.group("frac") or "")[:6].ljust(6, "0")
    tz_text = match.group("tz")
    if tz_text in (None, "Z"):
        tz = UTC
    else:
        sign = 1 if tz_text[0] == "+" else -1
        digits = tz_text[1:].replace(":", "")
        tz = timezone(sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:])))
    try:
        moment = datetime(
            int(match.group("y")),
            int(match.group("mo")),
            int(match.group("d")),
            int(match.group("h")),
            int(match.group("mi")),
            int(match.group("s")),
            int(fraction),
            tzinfo=tz,
        )
    except ValueError:
        return None
    return moment.timestamp()


def is_rewritable_path(path: str) -> bool:
    """单条目详情、列表、Resume、Latest 都重写；媒体流与其它接口不碰。"""
    match = _ITEM_PATH.match(path)
    if match is not None and match.group("item").lower() not in _RESERVED_ITEMS:
        return True
    return _LIST_PATH.match(path) is not None


def _upstream_has_record(user_data: dict[str, Any]) -> bool:
    """极影视这条到底有没有记录：已看、位置>0、或播放时间存在。"""
    if user_data.get("Played") is True:
        return True
    position = user_data.get("PlaybackPositionTicks")
    if isinstance(position, (int, float)) and not isinstance(position, bool) and position > 0:
        return True
    return bool(user_data.get("LastPlayedDate"))


def merge_user_data(
    item: dict[str, Any],
    local: LocalProgress | None,
    *,
    now: float | None = None,
    grace: float = 15.0,
) -> tuple[dict[str, Any], bool]:
    """以极影视为准：上游没记录且本地记录也旧了，就认为上游被清空。

    返回（合并后的条目, 是否需要清掉本地记录）。
    """
    if local is None:
        return item, False, False
    user_data = item.get("UserData")
    if not isinstance(user_data, dict):
        user_data = {}
    if _upstream_has_record(user_data):
        upstream_position = user_data.get("PlaybackPositionTicks")
        overridden = (
            isinstance(upstream_position, (int, float))
            and not isinstance(upstream_position, bool)
            and abs(upstream_position - local.position_ticks) >= 10_000_000
        )
        return item, False, overridden
    current = time.time() if now is None else now
    if current - local.updated_at > grace:
        # 上游明确没有这条记录，本地又早已写入 → 用户在极影视里清掉了，跟着清
        return item, True, False

    merged_data = dict(user_data)
    merged_data["PlaybackPositionTicks"] = local.position_ticks
    percentage = _played_percentage(local.position_ticks, item.get("RunTimeTicks"))
    if percentage is not None:
        merged_data["PlayedPercentage"] = percentage
    if local.played:
        merged_data["Played"] = True
    merged_item = dict(item)
    merged_item["UserData"] = merged_data
    return merged_item, False, False


def rewrite_payload(
    payload: Any,
    resolver: Callable[[str], LocalProgress | None],
    *,
    now: float | None = None,
    grace: float = 15.0,
    on_clear: Callable[[str], None] | None = None,
    on_override: Callable[[str], None] | None = None,
) -> Any:
    """递归重写所有带 Id + UserData 的条目；其余字段原样保留。"""
    return _walk(payload, resolver, time.time() if now is None else now, grace, on_clear, on_override)


def collect_runtimes(payload: Any) -> dict[str, int]:
    """收集响应里所有条目的运行时长，供进度上报时算百分比。"""
    found: dict[str, int] = {}
    _collect_runtimes(payload, found)
    return found


def _collect_runtimes(node: Any, found: dict[str, int]) -> None:
    if isinstance(node, dict):
        item_id = node.get("Id")
        runtime = node.get("RunTimeTicks")
        if isinstance(item_id, str) and isinstance(runtime, int) and not isinstance(runtime, bool) and runtime > 0:
            found[item_id] = runtime
        for value in node.values():
            _collect_runtimes(value, found)
    elif isinstance(node, list):
        for entry in node:
            _collect_runtimes(entry, found)


def _walk(
    node: Any,
    resolver: Callable[[str], LocalProgress | None],
    now: float,
    grace: float,
    on_clear: Callable[[str], None] | None,
    on_override: Callable[[str], None] | None = None,
) -> Any:
    if isinstance(node, dict):
        item_id = node.get("Id")
        if isinstance(item_id, str) and isinstance(node.get("UserData"), dict):
            merged, cleared, overridden = merge_user_data(node, resolver(item_id), now=now, grace=grace)
            if cleared and on_clear is not None:
                on_clear(item_id)
            if overridden and on_override is not None:
                on_override(item_id)
            node = merged
        return {key: _walk(value, resolver, now, grace, on_clear, on_override) for key, value in node.items()}
    if isinstance(node, list):
        return [_walk(entry, resolver, now, grace, on_clear, on_override) for entry in node]
    return node


def _played_percentage(position_ticks: int, runtime_ticks: Any) -> float | None:
    if not isinstance(runtime_ticks, (int, float)) or isinstance(runtime_ticks, bool):
        return None
    if runtime_ticks <= 0:
        return None
    return round(min(position_ticks / runtime_ticks * 100.0, 100.0), 2)
