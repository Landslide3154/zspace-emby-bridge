"""脱敏：日志与 /debug 输出里不允许出现任何凭据。"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MASK = "***"

# 请求头里要遮掉的名字（小写比较）
SENSITIVE_HEADERS = frozenset(
    {
        "x-emby-token",
        "x-mediabrowser-token",
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
    }
)

# JSON / query 里要遮掉的键名（小写比较）
SENSITIVE_KEYS = frozenset({"api_key", "apikey", "token", "access_token", "password"})

# 键名里带这些片段就按凭据处理：Hills 会把 X-Emby-Token 塞进 query，只认精确键名会漏
SENSITIVE_MARKERS = ("token", "api_key", "apikey", "password", "secret", "authorization")


def is_sensitive_name(name: str) -> bool:
    """判断头名/参数名/JSON 键是否属于凭据。"""
    lowered = name.lower()
    if lowered in SENSITIVE_HEADERS or lowered in SENSITIVE_KEYS:
        return True
    return any(marker in lowered for marker in SENSITIVE_MARKERS)


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """按头名脱敏，保留键名便于排查，值一律换成 ***。"""
    return {name: (MASK if is_sensitive_name(name) else value) for name, value in headers.items()}


def redact_json(value: Any) -> Any:
    """递归脱敏 JSON 结构；返回新对象，不修改调用方数据。"""
    if isinstance(value, dict):
        return {key: (MASK if is_sensitive_name(str(key)) else redact_json(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_json(item) for item in value]
    return value


def redact_url(url: str) -> str:
    """遮掉 URL 查询串里的凭据参数。"""
    parts = urlsplit(url)
    if not parts.query:
        return url
    query = [(key, MASK if is_sensitive_name(key) else val) for key, val in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit(parts._replace(query=urlencode(query, safe="*")))
