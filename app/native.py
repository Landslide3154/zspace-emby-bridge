"""极影视原生进度：直接更新 zvideo_playlist.play_duration 与 zvideo_list.state。

两种通道：
- local：容器里挂载了数据库文件，直接用 sqlite3 写；
- ssh：开发机通过 SSH + sudo 远程执行 sqlite3（数据文件属于 root）。
"""
from __future__ import annotations

import re
import shlex
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

_ID_RE = re.compile(r"^[0-9A-Za-z_-]{1,64}$")
# Emby 侧 item id 形如 collection_<collection_id>_<classification_id>
_EMBY_ITEM = re.compile(r"^collection_([0-9a-z]+)_([0-9a-f-]{32,})$", re.IGNORECASE)

PLAYED_STATE = 2  # zvideo_list.state：2 = 已看


@dataclass(frozen=True)
class WriteResult:
    changed: int
    reason: str = ""


class PlaylistWriter(Protocol):
    def write_position(
        self, collection_id: str, position_seconds: int, classification_id: str | None = None
    ) -> WriteResult: ...

    def mark_played(self, collection_id: str) -> WriteResult: ...


def parse_item_id(item_id: str) -> tuple[str, str] | None:
    """把 Emby 的 item id 拆成（collection_id, classification_id）。"""
    if not isinstance(item_id, str):
        return None
    match = _EMBY_ITEM.match(item_id)
    if match is None:
        return None
    return match.group(1), match.group(2)


def _checked(value: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ValueError(f"非法标识：{value!r}")
    return value


def _now_text() -> str:
    """极影视的时间戳形如 2026-10-26 13:02:16.227973883+08:00。"""
    moment = datetime.now().astimezone()
    offset = moment.strftime("%z")
    return f"{moment:%Y-%m-%d %H:%M:%S.%f}{offset[:3]}:{offset[3:]}"


def _valid_position(position_seconds: int) -> bool:
    return isinstance(position_seconds, int) and position_seconds >= 0


class LocalSqliteWriter:
    """数据库文件可写时（容器挂载）使用。"""

    def __init__(self, db_path: str, user_name: str) -> None:
        self._db_path = db_path
        self._user = _checked(user_name)

    def write_position(
        self, collection_id: str, position_seconds: int, classification_id: str | None = None
    ) -> WriteResult:
        target = _checked(collection_id)
        if not _valid_position(position_seconds):
            return WriteResult(0, "invalid_position")
        now = _now_text()
        connection = sqlite3.connect(self._db_path, timeout=10)
        try:
            connection.execute("PRAGMA busy_timeout=5000")
            with connection:
                cursor = connection.execute(
                    "UPDATE zvideo_playlist SET play_duration = ?, updated_at = ?"
                    " WHERE user_name = ? AND collection_id = ?",
                    (position_seconds, now, self._user, target),
                )
                if cursor.rowcount:
                    return WriteResult(cursor.rowcount)
                if not classification_id:
                    return WriteResult(0, "not_in_playlist")
                inserted = connection.execute(
                    "INSERT INTO zvideo_playlist (user_name, classification_id, collection_id, video_id,"
                    " name, path, play_duration, created_at, updated_at, video_duration)"
                    " SELECT ?, ?, ?, video_id, name, path, ?, ?, ?, duration FROM zvideo_list"
                    " WHERE user_name = ? AND collection_id = ? LIMIT 1",
                    (self._user, _checked(classification_id), target, position_seconds, now, now, self._user, target),
                )
                return WriteResult(inserted.rowcount, "" if inserted.rowcount else "not_in_library")
        finally:
            connection.close()

    def mark_played(self, collection_id: str) -> WriteResult:
        target = _checked(collection_id)
        now = _now_text()
        connection = sqlite3.connect(self._db_path, timeout=10)
        try:
            connection.execute("PRAGMA busy_timeout=5000")
            with connection:
                cursor = connection.execute(
                    "UPDATE zvideo_list SET state = ?, updated_at = ? WHERE user_name = ? AND collection_id = ?",
                    (PLAYED_STATE, now, self._user, target),
                )
                connection.execute(
                    "DELETE FROM zvideo_playlist WHERE user_name = ? AND collection_id = ?", (self._user, target)
                )
                return WriteResult(cursor.rowcount, "" if cursor.rowcount else "not_in_library")
        finally:
            connection.close()


class SshSqliteWriter:
    """开发机用：SSH + sudo 在 NAS 上执行同样的语句。"""

    def __init__(
        self,
        host: str,
        port: int,
        ssh_user: str,
        password: str,
        db_path: str,
        user_name: str,
    ) -> None:
        self._host = host
        self._port = port
        self._ssh_user = ssh_user
        self._password = password
        self._db_path = db_path
        self._user = _checked(user_name)

    def write_position(
        self, collection_id: str, position_seconds: int, classification_id: str | None = None
    ) -> WriteResult:
        target = _checked(collection_id)
        if not _valid_position(position_seconds):
            return WriteResult(0, "invalid_position")
        now = _now_text()
        script = (
            "PRAGMA busy_timeout=5000;"
            "BEGIN IMMEDIATE;"
            f"UPDATE zvideo_playlist SET play_duration={position_seconds}, updated_at='{now}'"
            f" WHERE user_name='{self._user}' AND collection_id='{target}';"
            "SELECT 'upd', changes();"
        )
        if classification_id:
            script += (
                "INSERT INTO zvideo_playlist (user_name, classification_id, collection_id, video_id, name, path,"
                f" play_duration, created_at, updated_at, video_duration)"
                f" SELECT '{self._user}', '{_checked(classification_id)}', '{target}', video_id, name, path,"
                f" {position_seconds}, '{now}', '{now}', duration FROM zvideo_list"
                f" WHERE user_name='{self._user}' AND collection_id='{target}'"
                f" AND NOT EXISTS (SELECT 1 FROM zvideo_playlist WHERE user_name='{self._user}'"
                f" AND collection_id='{target}') LIMIT 1;"
                "SELECT 'ins', changes();"
            )
        script += "COMMIT;"
        counts = self._counts(script)
        changed = counts.get("upd", 0) + counts.get("ins", 0)
        if changed:
            return WriteResult(changed)
        return WriteResult(0, "not_in_library")

    def mark_played(self, collection_id: str) -> WriteResult:
        target = _checked(collection_id)
        now = _now_text()
        script = (
            "PRAGMA busy_timeout=5000;"
            "BEGIN IMMEDIATE;"
            f"UPDATE zvideo_list SET state={PLAYED_STATE}, updated_at='{now}'"
            f" WHERE user_name='{self._user}' AND collection_id='{target}';"
            "SELECT 'mark', changes();"
            f"DELETE FROM zvideo_playlist WHERE user_name='{self._user}' AND collection_id='{target}';"
            "COMMIT;"
        )
        counts = self._counts(script)
        changed = counts.get("mark", 0)
        return WriteResult(changed, "" if changed else "not_in_library")

    def _counts(self, script: str) -> dict[str, int]:
        output = self._run(script)
        counts: dict[str, int] = {}
        for line in output.splitlines():
            label, _, value = line.partition("|")
            if value.strip().isdigit():
                counts[label.strip()] = int(value.strip())
        return counts

    def _run(self, sql: str) -> str:
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self._host,
                port=self._port,
                username=self._ssh_user,
                password=self._password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False,
            )
            command = f"sudo -S -p '' sqlite3 {shlex.quote(f'file:{self._db_path}?mode=rw')} {shlex.quote(sql)}"
            stdin, stdout, stderr = client.exec_command(command, timeout=20)
            stdin.write(self._password + "\n")
            stdin.flush()
            output = stdout.read().decode("utf-8", "replace")
            error = stderr.read().decode("utf-8", "replace")
        finally:
            client.close()
        if error.strip():
            raise RuntimeError(error.strip()[:300])
        return output


def build_writer(mode: str, **kwargs: object) -> PlaylistWriter | None:
    if not kwargs.get("user_name"):
        return None  # 没有用户标识就不写，避免写错人
    if mode == "local":
        return LocalSqliteWriter(str(kwargs["db_path"]), str(kwargs["user_name"]))
    if mode == "ssh":
        return SshSqliteWriter(
            host=str(kwargs["host"]),
            port=int(kwargs["port"]),
            ssh_user=str(kwargs["ssh_user"]),
            password=str(kwargs["password"]),
            db_path=str(kwargs["db_path"]),
            user_name=str(kwargs["user_name"]),
        )
    return None
