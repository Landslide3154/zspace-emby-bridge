"""运行时配置：面板可改，落 app_settings 表，改完立刻生效。"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace

from .config import Settings
from .store import ProgressStore

LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


@dataclass(frozen=True)
class Options:
    native_enabled: bool = True
    played_threshold: float = 0.9
    native_min_interval: float = 10.0
    sync_grace_seconds: float = 15.0
    sync_stream_prefs: bool = True
    collection_cover: bool = True
    log_level: str = "INFO"
    upstream_url: str = ""
    allowed_ips: str = ""


class RuntimeConfig:
    """env 提供默认值，面板写入的值优先生效。"""

    def __init__(self, store: ProgressStore, settings: Settings) -> None:
        self._store = store
        self._defaults = Options(
            native_enabled=settings.native_mode != "off",
            played_threshold=settings.played_threshold,
            native_min_interval=settings.native_min_interval,
            sync_grace_seconds=settings.sync_grace_seconds,
            sync_stream_prefs=settings.sync_stream_prefs,
            collection_cover=settings.collection_cover,
            log_level=settings.log_level,
            upstream_url=settings.upstream_url,
            allowed_ips=settings.allowed_ips,
        )
        self._options = self._defaults
        self.reload()

    @property
    def options(self) -> Options:
        return self._options

    def reload(self) -> None:
        stored = self._store.get_settings()
        options = self._options
        if "native_enabled" in stored:
            options = replace(options, native_enabled=_as_bool(stored["native_enabled"], options.native_enabled))
        if "played_threshold" in stored:
            options = replace(options, played_threshold=_as_float(stored["played_threshold"], options.played_threshold))
        if "native_min_interval" in stored:
            options = replace(
                options, native_min_interval=_as_float(stored["native_min_interval"], options.native_min_interval)
            )
        if "sync_grace_seconds" in stored:
            options = replace(
                options, sync_grace_seconds=_as_float(stored["sync_grace_seconds"], options.sync_grace_seconds)
            )
        if "sync_stream_prefs" in stored:
            options = replace(
                options, sync_stream_prefs=_as_bool(stored["sync_stream_prefs"], options.sync_stream_prefs)
            )
        if "collection_cover" in stored:
            options = replace(
                options, collection_cover=_as_bool(stored["collection_cover"], options.collection_cover)
            )
        if "log_level" in stored and stored["log_level"].upper() in LOG_LEVELS:
            options = replace(options, log_level=stored["log_level"].upper())
        if "upstream_url" in stored:
            value = _as_str(stored["upstream_url"], options.upstream_url)
            if value.startswith(("http://", "https://")):
                options = replace(options, upstream_url=value.rstrip("/"))
        if "allowed_ips" in stored:
            options = replace(options, allowed_ips=_as_str(stored["allowed_ips"], options.allowed_ips))
        self._options = options
        logging.getLogger("bridge").setLevel(options.log_level)

    def reset(self) -> Options:
        """清掉面板里的覆盖值，回到环境变量默认。"""
        keys = ["native_enabled", "played_threshold", "native_min_interval",
                "sync_grace_seconds", "sync_stream_prefs", "collection_cover", "log_level",
                "upstream_url", "allowed_ips"]
        self._store.delete_settings(keys)
        self._options = self._defaults
        logging.getLogger("bridge").setLevel(self._options.log_level)
        return self._options

    def update(self, **changes: object) -> Options:
        options = self._options
        if "native_enabled" in changes:
            options = replace(options, native_enabled=bool(changes["native_enabled"]))
        if "played_threshold" in changes:
            threshold = float(changes["played_threshold"])  # type: ignore[arg-type]
            if not 0.0 <= threshold <= 1.0:
                raise ValueError("已看阈值必须在 0 到 1 之间")
            options = replace(options, played_threshold=threshold)
        if "native_min_interval" in changes:
            interval = float(changes["native_min_interval"])  # type: ignore[arg-type]
            if interval < 0:
                raise ValueError("写入间隔不能为负")
            options = replace(options, native_min_interval=interval)
        if "sync_grace_seconds" in changes:
            grace = float(changes["sync_grace_seconds"])  # type: ignore[arg-type]
            if grace < 0:
                raise ValueError("同步宽限期不能为负")
            options = replace(options, sync_grace_seconds=grace)
        if "sync_stream_prefs" in changes:
            options = replace(options, sync_stream_prefs=bool(changes["sync_stream_prefs"]))
        if "collection_cover" in changes:
            options = replace(options, collection_cover=bool(changes["collection_cover"]))
        if "log_level" in changes:
            level = str(changes["log_level"]).upper()
            if level not in LOG_LEVELS:
                raise ValueError("日志级别不合法")
            options = replace(options, log_level=level)
        if "upstream_url" in changes:
            url = str(changes["upstream_url"]).strip().rstrip("/")
            if not url.startswith(("http://", "https://")):
                raise ValueError("上游地址必须以 http:// 或 https:// 开头")
            options = replace(options, upstream_url=url)
        if "allowed_ips" in changes:
            options = replace(options, allowed_ips=str(changes["allowed_ips"]).strip())

        self._store.put_settings({key: json.dumps(value) for key, value in _as_dict(options).items()})
        self._options = options
        logging.getLogger("bridge").setLevel(options.log_level)
        return options


def _as_dict(options: Options) -> dict[str, object]:
    return {
        "native_enabled": options.native_enabled,
        "played_threshold": options.played_threshold,
        "native_min_interval": options.native_min_interval,
        "sync_grace_seconds": options.sync_grace_seconds,
        "sync_stream_prefs": options.sync_stream_prefs,
        "collection_cover": options.collection_cover,
        "log_level": options.log_level,
        "upstream_url": options.upstream_url,
        "allowed_ips": options.allowed_ips,
    }


def _as_bool(raw: str, default: bool) -> bool:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return default
    return bool(value) if isinstance(value, bool) else default


def _as_str(raw: str, default: str) -> str:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return default
    return value if isinstance(value, str) else default


def _as_float(raw: str, default: float) -> float:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return default
    return float(value) if isinstance(value, (int, float)) else default
