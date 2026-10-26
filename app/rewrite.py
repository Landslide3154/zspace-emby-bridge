"""UserData 重写与新旧进度合并。"""
from __future__ import annotations

import re
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


def merge_user_data(item: dict[str, Any], local: LocalProgress | None) -> dict[str, Any]:
    """本地更新更晚才覆盖；否则保留极影视返回的值。不修改入参。"""
    if local is None:
        return item
    user_data = item.get("UserData")
    if not isinstance(user_data, dict):
        user_data = {}
    upstream_updated = parse_iso8601(user_data.get("LastPlayedDate"))
    if upstream_updated is not None and upstream_updated > local.updated_at:
        return item

    merged_data = dict(user_data)
    merged_data["PlaybackPositionTicks"] = local.position_ticks
    percentage = _played_percentage(local.position_ticks, item.get("RunTimeTicks"))
    if percentage is not None:
        merged_data["PlayedPercentage"] = percentage
    if local.played:
        merged_data["Played"] = True

    merged_item = dict(item)
    merged_item["UserData"] = merged_data
    return merged_item


def rewrite_payload(payload: Any, resolver: Callable[[str], LocalProgress | None]) -> Any:
    """递归重写所有带 Id + UserData 的条目；其余字段原样保留。"""
    return _walk(payload, resolver)


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


def _walk(node: Any, resolver: Callable[[str], LocalProgress | None]) -> Any:
    if isinstance(node, dict):
        item_id = node.get("Id")
        if isinstance(item_id, str) and isinstance(node.get("UserData"), dict):
            node = merge_user_data(node, resolver(item_id))
        return {key: _walk(value, resolver) for key, value in node.items()}
    if isinstance(node, list):
        return [_walk(entry, resolver) for entry in node]
    return node


def _played_percentage(position_ticks: int, runtime_ticks: Any) -> float | None:
    if not isinstance(runtime_ticks, (int, float)) or isinstance(runtime_ticks, bool):
        return None
    if runtime_ticks <= 0:
        return None
    return round(min(position_ticks / runtime_ticks * 100.0, 100.0), 2)
