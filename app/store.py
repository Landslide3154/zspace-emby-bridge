"""进度存储：SQLite（WAL），按 token 哈希 + ItemId 隔离。"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .proxy import ProgressEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS progress (
    token_hash     TEXT    NOT NULL,
    item_id        TEXT    NOT NULL,
    user_id        TEXT,
    position_ticks INTEGER NOT NULL,
    played         INTEGER NOT NULL DEFAULT 0,
    updated_at     REAL    NOT NULL,
    last_path      TEXT,
    play_session_id TEXT,
    body_format    TEXT,
    body_summary   TEXT,
    PRIMARY KEY (token_hash, item_id)
);
CREATE INDEX IF NOT EXISTS idx_progress_updated_at ON progress(updated_at DESC);
CREATE TABLE IF NOT EXISTS item_runtime (
    item_id       TEXT PRIMARY KEY,
    runtime_ticks INTEGER NOT NULL,
    updated_at    REAL NOT NULL
);
"""


def token_hash(token: str) -> str:
    """只存哈希：库里和日志里都不出现原始 token。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class StoredProgress:
    token_hash: str
    item_id: str
    user_id: str | None
    position_ticks: int
    played: bool
    updated_at: float


class ProgressStore:
    """短事务写入；连接被多个协程复用，用锁串行化。"""

    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)

    def journal_mode(self) -> str:
        with self._lock:
            return str(self._conn.execute("PRAGMA journal_mode").fetchone()[0])

    def record(self, event: "ProgressEvent", token_id: str, user_id: str | None) -> None:
        """落一条上报；缺 PositionTicks 或“立刻退出报 0”的情况不写。"""
        ticks = event.position_ticks
        if ticks is None or not event.item_id:
            return
        if ticks == 0 and event.path.rstrip("/").lower().endswith("/stopped"):
            return
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO progress (token_hash, item_id, user_id, position_ticks, played, updated_at,
                                      last_path, play_session_id, body_format, body_summary)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
                ON CONFLICT(token_hash, item_id) DO UPDATE SET
                    position_ticks = excluded.position_ticks,
                    user_id = COALESCE(excluded.user_id, progress.user_id),
                    updated_at = excluded.updated_at,
                    last_path = excluded.last_path,
                    play_session_id = excluded.play_session_id,
                    body_format = excluded.body_format,
                    body_summary = excluded.body_summary
                """,
                (
                    token_id,
                    event.item_id,
                    user_id,
                    ticks,
                    event.received_at,
                    event.path,
                    event.play_session_id,
                    event.body_format,
                    event.body_summary,
                ),
            )

    def get(self, token_id: str, item_id: str) -> StoredProgress | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM progress WHERE token_hash = ? AND item_id = ?", (token_id, item_id)
            ).fetchone()
        return _to_record(row) if row is not None else None

    def save_runtimes(self, runtimes: dict[str, int]) -> None:
        """缓存条目时长：进度上报时用来算百分比，进而决定是否回写“已看”。"""
        if not runtimes:
            return
        now = time.time()
        rows = [(item_id, int(ticks), now) for item_id, ticks in runtimes.items()]
        with self._lock:
            self._conn.executemany(
                """
                INSERT INTO item_runtime (item_id, runtime_ticks, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    runtime_ticks = excluded.runtime_ticks,
                    updated_at = excluded.updated_at
                """,
                rows,
            )

    def get_runtime(self, item_id: str) -> int | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT runtime_ticks FROM item_runtime WHERE item_id = ?", (item_id,)
            ).fetchone()
        return int(row["runtime_ticks"]) if row is not None else None

    def claim_played(self, token_id: str, item_id: str) -> bool:
        """把“已看回写”做成一次性：只有第一次返回 True。"""
        with self._lock:
            row = self._conn.execute(
                "SELECT played FROM progress WHERE token_hash = ? AND item_id = ?", (token_id, item_id)
            ).fetchone()
            if row is None or row["played"]:
                return False
            self._conn.execute(
                "UPDATE progress SET played = 1 WHERE token_hash = ? AND item_id = ?", (token_id, item_id)
            )
            return True

    def recent(self, limit: int = 20) -> list[dict]:
        if limit <= 0:
            return []
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM progress ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_to_dict(row) for row in rows]

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM progress").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _to_record(row: sqlite3.Row) -> StoredProgress:
    return StoredProgress(
        token_hash=row["token_hash"],
        item_id=row["item_id"],
        user_id=row["user_id"],
        position_ticks=int(row["position_ticks"]),
        played=bool(row["played"]),
        updated_at=float(row["updated_at"]),
    )


def _to_dict(row: sqlite3.Row) -> dict:
    return {
        "item_id": row["item_id"],
        "user_id": row["user_id"],
        "position_ticks": int(row["position_ticks"]),
        "has_position_ticks": True,
        "played": bool(row["played"]),
        "path": row["last_path"],
        "play_session_id": row["play_session_id"],
        "body_format": row["body_format"],
        "body_summary": row["body_summary"],
        "received_at": datetime.fromtimestamp(float(row["updated_at"]), UTC).isoformat(),
    }
