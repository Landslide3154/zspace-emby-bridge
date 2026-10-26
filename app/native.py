"""极影视原生进度：直接更新 zvideo_playlist / zvideo_list。

- collection_<collection_id>_<classification>：整部影片 / 合集
- video_<video_id>_<collection_id>_<classification>：合集里的单个文件（剧集、单文件条目…）

生产用 local 模式（容器挂载库文件）；ssh 模式仅供开发机调试，只支持上面两种 id。
"""
from __future__ import annotations

import re
import shlex
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

_ID_RE = re.compile(r"^[0-9A-Za-z_-]{1,64}$")
_COLLECTION_ITEM = re.compile(r"^collection_([0-9a-z]+)_([0-9a-f-]{32,})$", re.IGNORECASE)
_VIDEO_ITEM = re.compile(r"^video_([0-9a-z]+)_([0-9a-z]+)_([0-9a-f-]{32,})$", re.IGNORECASE)

PLAYED_STATE = 2  # zvideo_list.state：2 = 已看


@dataclass(frozen=True)
class ParsedItem:
    collection_id: str
    classification_id: str
    video_id: str | None = None


@dataclass(frozen=True)
class WriteResult:
    changed: int
    reason: str = ""


class PlaylistWriter(Protocol):
    def resolve(self, item_id: str) -> ParsedItem | None: ...

    def write_position(
        self,
        item: ParsedItem,
        position_seconds: int,
        *,
        audio_index: int | None = None,
        subtitle_index: int | None = None,
    ) -> WriteResult: ...

    def mark_played(self, item: ParsedItem) -> WriteResult: ...

    def list_skips(self, collection_id: str) -> list[dict]: ...


def parse_item_id(item_id: str) -> ParsedItem | None:
    """只做格式识别；识别不了的交由 writer.resolve 用数据库兜底。"""
    if not isinstance(item_id, str):
        return None
    video = _VIDEO_ITEM.match(item_id)
    if video is not None:
        return ParsedItem(collection_id=video.group(2), classification_id=video.group(3), video_id=video.group(1))
    collection = _COLLECTION_ITEM.match(item_id)
    if collection is not None:
        return ParsedItem(collection_id=collection.group(1), classification_id=collection.group(2))
    return None


def _checked(value: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ValueError(f"非法标识：{value!r}")
    return value


def _now_text() -> str:
    moment = datetime.now().astimezone()
    offset = moment.strftime("%z")
    return f"{moment:%Y-%m-%d %H:%M:%S.%f}{offset[:3]}:{offset[3:]}"


class LocalSqliteWriter:
    """数据库文件可写时（容器挂载）使用。"""

    def __init__(self, db_path: str, user_name: str) -> None:
        self._db_path = db_path
        self._user = _checked(user_name)

    def resolve(self, item_id: str) -> ParsedItem | None:
        parsed = parse_item_id(item_id)
        if parsed is not None:
            return parsed
        tokens = [token for token in re.split(r"[_\-]", item_id) if token and _ID_RE.match(token)]
        connection = self._connect()
        try:
            for token in tokens:
                row = connection.execute(
                    "SELECT collection_id, video_id FROM zvideo_list WHERE user_name = ?"
                    " AND (collection_id = ? OR video_id = ?) LIMIT 1",
                    (self._user, token, token),
                ).fetchone()
                if row is None:
                    continue
                classification = connection.execute(
                    "SELECT classification_id FROM zvideo_playlist WHERE user_name = ? AND collection_id = ? LIMIT 1",
                    (self._user, row["collection_id"]),
                ).fetchone()
                if classification is None:
                    continue
                video_id = row["video_id"] if row["video_id"] == token else None
                return ParsedItem(
                    collection_id=row["collection_id"],
                    classification_id=classification["classification_id"],
                    video_id=video_id,
                )
        finally:
            connection.close()
        return None

    def write_position(
        self,
        item: ParsedItem,
        position_seconds: int,
        *,
        audio_index: int | None = None,
        subtitle_index: int | None = None,
    ) -> WriteResult:
        if not isinstance(position_seconds, int) or position_seconds < 0:
            return WriteResult(0, "invalid_position")
        collection_id = _checked(item.collection_id)
        now = _now_text()
        connection = self._connect()
        try:
            with connection:
                meta = self._meta(connection, collection_id, item.video_id)
                cursor = connection.execute(
                    "UPDATE zvideo_playlist SET play_duration = ?, updated_at = ?,"
                    " video_id = COALESCE(?, video_id), name = COALESCE(?, name),"
                    " path = COALESCE(?, path), video_duration = COALESCE(?, video_duration),"
                    " audio_index = COALESCE(?, audio_index), subtitle_index = COALESCE(?, subtitle_index)"
                    " WHERE user_name = ? AND collection_id = ?",
                    (
                        position_seconds,
                        now,
                        meta[0],
                        meta[1],
                        meta[2],
                        meta[3],
                        audio_index,
                        subtitle_index,
                        self._user,
                        collection_id,
                    ),
                )
                if cursor.rowcount:
                    return WriteResult(cursor.rowcount)
                if meta[0] is None:
                    return WriteResult(0, "not_in_playlist")
                inserted = connection.execute(
                    "INSERT INTO zvideo_playlist (user_name, classification_id, collection_id, video_id, name, path,"
                    " play_duration, created_at, updated_at, video_duration, audio_index, subtitle_index)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        self._user,
                        _checked(item.classification_id),
                        collection_id,
                        meta[0],
                        meta[1],
                        meta[2],
                        position_seconds,
                        now,
                        now,
                        meta[3],
                        audio_index,
                        subtitle_index,
                    ),
                )
                return WriteResult(inserted.rowcount, "" if inserted.rowcount else "not_in_library")
        finally:
            connection.close()

    def mark_played(self, item: ParsedItem) -> WriteResult:
        collection_id = _checked(item.collection_id)
        now = _now_text()
        connection = self._connect()
        try:
            with connection:
                if item.video_id:
                    cursor = connection.execute(
                        "UPDATE zvideo_list SET state = ?, updated_at = ?"
                        " WHERE user_name = ? AND collection_id = ? AND video_id = ?",
                        (PLAYED_STATE, now, self._user, collection_id, _checked(item.video_id)),
                    )
                else:
                    cursor = connection.execute(
                        "UPDATE zvideo_list SET state = ?, updated_at = ? WHERE user_name = ? AND collection_id = ?",
                        (PLAYED_STATE, now, self._user, collection_id),
                    )
                connection.execute(
                    "DELETE FROM zvideo_playlist WHERE user_name = ? AND collection_id = ?",
                    (self._user, collection_id),
                )
                return WriteResult(cursor.rowcount, "" if cursor.rowcount else "not_in_library")
        finally:
            connection.close()

    def lookup(self, item_ids: list[str]) -> dict[str, dict]:
        """返回每个 item 的片名与文件名，取不到就留空。"""
        found: dict[str, dict] = {}
        connection = self._connect()
        try:
            for item_id in item_ids:
                parsed = parse_item_id(item_id)
                if parsed is None:
                    continue
                collection = connection.execute(
                    "SELECT title FROM zvideo_collection WHERE user_name = ? AND collection_id = ? LIMIT 1",
                    (self._user, parsed.collection_id),
                ).fetchone()
                if parsed.video_id:
                    episode = connection.execute(
                        "SELECT name FROM zvideo_list WHERE user_name = ? AND collection_id = ? AND video_id = ? LIMIT 1",
                        (self._user, parsed.collection_id, parsed.video_id),
                    ).fetchone()
                else:
                    episode = connection.execute(
                        "SELECT name FROM zvideo_list WHERE user_name = ? AND collection_id = ? LIMIT 1",
                        (self._user, parsed.collection_id),
                    ).fetchone()
                found[item_id] = {
                    "title": collection["title"] if collection else None,
                    "file": episode["name"] if episode else None,
                }
        finally:
            connection.close()
        return found

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """按 collection_id、片名或文件名找条目。"""
        text = (query or "").strip()
        if not text:
            return []
        connection = self._connect()
        try:
            if re.fullmatch(r"[0-9a-fA-F]{6,32}", text):
                rows = connection.execute(
                    "SELECT c.collection_id, c.title, l.video_id, l.name FROM zvideo_collection c"
                    " LEFT JOIN zvideo_list l ON l.user_name = c.user_name AND l.collection_id = c.collection_id"
                    " WHERE c.user_name = ? AND c.collection_id = ? LIMIT ?",
                    (self._user, text, limit),
                ).fetchall()
            else:
                like = f"%{text}%"
                rows = connection.execute(
                    "SELECT c.collection_id, c.title, l.video_id, l.name FROM zvideo_collection c"
                    " LEFT JOIN zvideo_list l ON l.user_name = c.user_name AND l.collection_id = c.collection_id"
                    " WHERE c.user_name = ? AND (c.title LIKE ? OR l.name LIKE ?)"
                    " GROUP BY c.collection_id ORDER BY MAX(c.updated) DESC LIMIT ?",
                    (self._user, like, like, limit),
                ).fetchall()
        finally:
            connection.close()
        return [
            {
                "collection_id": row["collection_id"],
                "video_id": row["video_id"],
                "title": row["title"],
                "file": row["name"],
            }
            for row in rows
        ]

    def list_skips(self, collection_id: str) -> list[dict]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT start_time, end_time FROM zvideo_skip WHERE collection_id = ?", (collection_id,)
            ).fetchall()
            return [{"start": row["start_time"], "end": row["end_time"]} for row in rows]
        except sqlite3.Error:
            return []
        finally:
            connection.close()

    def first_video_id(self, collection_id: str) -> str | None:
        """合集里「第一个添加」的条目（按自增 id 升序），用作兜底封面来源。"""
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT video_id FROM zvideo_list"
                " WHERE user_name = ? AND collection_id = ?"
                " ORDER BY id LIMIT 1",
                (self._user, _checked(collection_id)),
            ).fetchone()
        except sqlite3.Error:
            return None
        finally:
            connection.close()
        return row["video_id"] if row is not None else None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _meta(
        self, connection: sqlite3.Connection, collection_id: str, video_id: str | None
    ) -> tuple[str | None, str | None, str | None, int | None]:
        """取这一条（剧集是当前集）的 video_id/name/path/duration。"""
        if video_id:
            row = connection.execute(
                "SELECT video_id, name, path, duration FROM zvideo_list"
                " WHERE user_name = ? AND collection_id = ? AND video_id = ? LIMIT 1",
                (self._user, collection_id, _checked(video_id)),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT video_id, name, path, duration FROM zvideo_list"
                " WHERE user_name = ? AND collection_id = ? LIMIT 1",
                (self._user, collection_id),
            ).fetchone()
        if row is None:
            return (None, None, None, None)
        return (row["video_id"], row["name"], row["path"], row["duration"])


class SshSqliteWriter:
    """开发机调试用：SSH + sudo 远程执行。只支持两种标准 id，不做数据库兜底。"""

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

    def resolve(self, item_id: str) -> ParsedItem | None:
        return parse_item_id(item_id)

    def write_position(
        self,
        item: ParsedItem,
        position_seconds: int,
        *,
        audio_index: int | None = None,
        subtitle_index: int | None = None,
    ) -> WriteResult:
        if not isinstance(position_seconds, int) or position_seconds < 0:
            return WriteResult(0, "invalid_position")
        now = _now_text()
        collection_id = _checked(item.collection_id)
        video_clause = f"video_id='{_checked(item.video_id)}'" if item.video_id else "1=1"
        script = (
            "PRAGMA busy_timeout=5000;BEGIN IMMEDIATE;"
            f"UPDATE zvideo_playlist SET play_duration={position_seconds}, updated_at='{now}'"
            f" WHERE user_name='{self._user}' AND collection_id='{collection_id}';"
            "SELECT 'upd', changes();"
            "INSERT INTO zvideo_playlist (user_name, classification_id, collection_id, video_id, name, path,"
            " play_duration, created_at, updated_at, video_duration)"
            f" SELECT '{self._user}','{_checked(item.classification_id)}','{collection_id}', video_id, name, path,"
            f" {position_seconds}, '{now}', '{now}', duration FROM zvideo_list"
            f" WHERE user_name='{self._user}' AND collection_id='{collection_id}' AND {video_clause}"
            f" AND NOT EXISTS (SELECT 1 FROM zvideo_playlist WHERE user_name='{self._user}'"
            f" AND collection_id='{collection_id}') LIMIT 1;"
            "SELECT 'ins', changes();COMMIT;"
        )
        counts = self._counts(script)
        changed = counts.get("upd", 0) + counts.get("ins", 0)
        return WriteResult(changed, "" if changed else "not_in_library")

    def mark_played(self, item: ParsedItem) -> WriteResult:
        now = _now_text()
        collection_id = _checked(item.collection_id)
        scope = f" AND video_id='{_checked(item.video_id)}'" if item.video_id else ""
        script = (
            "PRAGMA busy_timeout=5000;BEGIN IMMEDIATE;"
            f"UPDATE zvideo_list SET state={PLAYED_STATE}, updated_at='{now}'"
            f" WHERE user_name='{self._user}' AND collection_id='{collection_id}'{scope};"
            "SELECT 'mark', changes();"
            f"DELETE FROM zvideo_playlist WHERE user_name='{self._user}' AND collection_id='{collection_id}';"
            "COMMIT;"
        )
        counts = self._counts(script)
        changed = counts.get("mark", 0)
        return WriteResult(changed, "" if changed else "not_in_library")

    def lookup(self, item_ids: list[str]) -> dict[str, dict]:
        return {item_id: {"title": None, "file": None} for item_id in item_ids if parse_item_id(item_id)}

    def search(self, query: str, limit: int = 20) -> list[dict]:
        return []

    def list_skips(self, collection_id: str) -> list[dict]:
        return []

    def first_video_id(self, collection_id: str) -> str | None:
        try:
            output = self._run(
                "SELECT video_id FROM zvideo_list"
                f" WHERE user_name = '{_checked(self._user)}'"
                f" AND collection_id = '{_checked(collection_id)}'"
                " ORDER BY id LIMIT 1;"
            )
        except RuntimeError:
            return None
        return output.strip() or None

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
        return None
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
