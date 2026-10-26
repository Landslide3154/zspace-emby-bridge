"""配置：全部来自环境变量，缺失时有明确默认值与校验。"""
from __future__ import annotations

import pytest

from app.config import Settings


def test_defaults() -> None:
    s = Settings.from_env({})
    assert s.upstream_url == "http://192.168.2.8:8021"
    assert s.listen_port == 8022
    assert s.log_level == "INFO"
    assert s.played_threshold == 0.9
    assert s.db_path.endswith(".db")


def test_env_overrides_and_url_normalized() -> None:
    s = Settings.from_env(
        {
            "UPSTREAM_URL": "http://10.0.0.9:8021/",
            "LISTEN_PORT": "9100",
            "DB_PATH": "data/x.db",
            "LOG_LEVEL": "debug",
            "PLAYED_THRESHOLD": "0.95",
        }
    )
    assert s.upstream_url == "http://10.0.0.9:8021"
    assert s.listen_port == 9100
    assert s.db_path == "data/x.db"
    assert s.log_level == "DEBUG"
    assert s.played_threshold == 0.95


def test_invalid_port_rejected() -> None:
    with pytest.raises(ValueError):
        Settings.from_env({"LISTEN_PORT": "not-a-port"})


def test_threshold_out_of_range_rejected() -> None:
    with pytest.raises(ValueError):
        Settings.from_env({"PLAYED_THRESHOLD": "1.5"})
