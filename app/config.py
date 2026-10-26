"""运行期配置：全部来自环境变量，默认值与校验集中在这一处。"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_UPSTREAM = "http://192.168.2.8:8021"
DEFAULT_DB_PATH = "data/progress.db"


@dataclass(frozen=True)
class Settings:
    upstream_url: str
    listen_port: int
    db_path: str
    log_level: str
    tz: str
    played_threshold: float

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        """从环境变量读配置；传入 env 便于单测，不传则读 os.environ。"""
        source = os.environ if env is None else env
        upstream = (source.get("UPSTREAM_URL") or DEFAULT_UPSTREAM).strip().rstrip("/")
        if not upstream.startswith(("http://", "https://")):
            raise ValueError(f"UPSTREAM_URL 必须是 http(s) 地址，当前为 {upstream!r}")

        port = _int_value(source.get("LISTEN_PORT"), 8022, "LISTEN_PORT")
        if not 0 < port < 65536:
            raise ValueError(f"LISTEN_PORT 越界：{port}")

        threshold = _float_value(source.get("PLAYED_THRESHOLD"), 0.9, "PLAYED_THRESHOLD")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"PLAYED_THRESHOLD 必须在 0 到 1 之间：{threshold}")

        return cls(
            upstream_url=upstream,
            listen_port=port,
            db_path=(source.get("DB_PATH") or DEFAULT_DB_PATH).strip(),
            log_level=(source.get("LOG_LEVEL") or "INFO").strip().upper(),
            tz=(source.get("TZ") or "Asia/Shanghai").strip(),
            played_threshold=threshold,
        )


def _int_value(raw: str | None, default: int, name: str) -> int:
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} 不是整数：{raw!r}") from exc


def _float_value(raw: str | None, default: float, name: str) -> float:
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} 不是数字：{raw!r}") from exc
