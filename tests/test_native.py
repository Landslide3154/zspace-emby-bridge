"""写极影视数据库：进度、建档、已看、剧集与 id 兜底解析。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.native import LocalSqliteWriter, ParsedItem, parse_item_id

SCHEMA = """
CREATE TABLE zvideo_playlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name varchar,
    classification_id varchar,
    collection_id varchar,
    video_id varchar,
    name varchar,
    path varchar,
    play_duration integer,
    created_at datetime,
    updated_at datetime,
    video_duration integer,
    audio_index text,
    subtitle_index text
);
CREATE UNIQUE INDEX user_playlist ON zvideo_playlist (user_name, classification_id, collection_id);
CREATE TABLE zvideo_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name varchar,
    video_id varchar,
    collection_id varchar,
    episode smallint,
    name varchar,
    path varchar,
    duration integer,
    state tinyint default 1,
    updated_at datetime
);
CREATE TABLE zvideo_skip (
    collection_id varchar,
    start_time integer,
    end_time integer
);
"""

USER = "17611545258"
COLLECTION = "560a79a3e816b6e"          # 电影
SERIES = "a2b7ae6735d2082"              # 剧集
CLASSIFICATION = "484e30ab-18be-4c7a-a6dd-e7105cad7e48"
SERIES_CLASSIFICATION = "91731175-242d-42dc-ac94-515229b46029"
VIDEO = "d6655bdf0f99f55"
MOVIE_ITEM = f"collection_{COLLECTION}_{CLASSIFICATION}"
EPISODE_ITEM = f"video_{VIDEO}_{SERIES}_{SERIES_CLASSIFICATION}"


def make_db(path: Path, position: int = 100) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO zvideo_list (user_name, video_id, collection_id, episode, name, path, duration, state)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (USER, "7d2002151cff985", COLLECTION, 0, "后室.mkv", "/media/a.mkv", 6636, 1),
    )
    conn.execute(
        "INSERT INTO zvideo_list (user_name, video_id, collection_id, episode, name, path, duration, state)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (USER, VIDEO, SERIES, 1, "蓝色星球 S02E01.mkv", "/media/blue/e1.mkv", 3075, 1),
    )
    conn.execute(
        "INSERT INTO zvideo_playlist (user_name, classification_id, collection_id, video_id, name, path,"
        " play_duration, created_at, updated_at, video_duration) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (USER, CLASSIFICATION, COLLECTION, "7d2002151cff985", "后室.mkv", "/media/a.mkv", position,
         "2026-10-26 12:00:00", "2026-10-26 12:00:00", 6636),
    )
    conn.commit()
    conn.close()
    return path


def test_parse_item_id_forms() -> None:
    assert parse_item_id(MOVIE_ITEM) == ParsedItem(COLLECTION, CLASSIFICATION)
    episode = parse_item_id(EPISODE_ITEM)
    assert episode == ParsedItem(SERIES, SERIES_CLASSIFICATION, VIDEO)
    assert parse_item_id("weird-id") is None
    assert parse_item_id("") is None


def test_resolve_falls_back_to_database(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    writer.write_position(ParsedItem(SERIES, SERIES_CLASSIFICATION, VIDEO), 10)
    unknown = f"episode_{VIDEO}_{SERIES}"
    resolved = writer.resolve(unknown)
    assert resolved is not None
    assert resolved.collection_id == SERIES
    assert resolved.video_id == VIDEO


def test_updates_position_and_episode_metadata(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.write_position(ParsedItem(SERIES, SERIES_CLASSIFICATION, VIDEO), 900)
    assert result.changed == 1
    row = sqlite3.connect(db).execute(
        "SELECT play_duration, video_id, name, video_duration FROM zvideo_playlist WHERE collection_id = ?",
        (SERIES,),
    ).fetchone()
    assert row[0] == 900
    assert row[1] == VIDEO
    assert row[2] == "蓝色星球 S02E01.mkv"
    assert row[3] == 3075


def test_updates_timestamp(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    writer.write_position(ParsedItem(COLLECTION, CLASSIFICATION), 1800)
    row = sqlite3.connect(db).execute(
        "SELECT play_duration, updated_at FROM zvideo_playlist WHERE collection_id = ?", (COLLECTION,)
    ).fetchone()
    assert row[0] == 1800
    assert row[1] != "2026-10-26 12:00:00"


def test_writes_stream_indexes_when_given(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    writer.write_position(ParsedItem(COLLECTION, CLASSIFICATION), 60, audio_index=2, subtitle_index=4)
    row = sqlite3.connect(db).execute(
        "SELECT audio_index, subtitle_index FROM zvideo_playlist WHERE collection_id = ?", (COLLECTION,)
    ).fetchone()
    assert (int(row[0]), int(row[1])) == (2, 4)


def test_writes_to_other_user_untouched(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), "someone-else")
    result = writer.write_position(ParsedItem(COLLECTION, CLASSIFICATION), 1800)
    assert result.changed == 0
    assert result.reason in {"not_in_playlist", "not_in_library"}


def test_missing_item_is_reported_not_created(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.write_position(ParsedItem("deadbeefcafe", CLASSIFICATION), 60)
    assert result.changed == 0
    assert result.reason == "not_in_playlist"


def test_rejects_unsafe_identifiers(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    with pytest.raises(ValueError):
        writer.write_position(ParsedItem("x'; DROP TABLE zvideo_playlist; --", CLASSIFICATION), 10)


def test_negative_position_is_ignored(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.write_position(ParsedItem(COLLECTION, CLASSIFICATION), -5)
    assert result.changed == 0
    assert result.reason == "invalid_position"


def test_mark_played_marks_only_that_episode(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO zvideo_list (user_name, video_id, collection_id, episode, name, path, duration, state)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (USER, "3972c374921b4b9", SERIES, 2, "E02.mkv", "/media/blue/e2.mkv", 3211, 1),
    )
    conn.commit()
    conn.close()
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.mark_played(ParsedItem(SERIES, SERIES_CLASSIFICATION, VIDEO))
    assert result.changed == 1
    rows = sqlite3.connect(db).execute(
        "SELECT video_id, state FROM zvideo_list WHERE collection_id = ? ORDER BY episode", (SERIES,)
    ).fetchall()
    assert rows == [(VIDEO, 2), ("3972c374921b4b9", 1)]


def test_mark_played_series_marks_all_episodes(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.mark_played(ParsedItem(SERIES, SERIES_CLASSIFICATION))
    assert result.changed == 1
    writer.mark_played(ParsedItem(COLLECTION, CLASSIFICATION))
    states = sqlite3.connect(db).execute("SELECT state FROM zvideo_list").fetchall()
    assert all(state == 2 for (state,) in states)


def test_list_skips(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO zvideo_skip (collection_id, start_time, end_time) VALUES (?,?,?)", (COLLECTION, 10, 80))
    conn.commit()
    conn.close()
    writer = LocalSqliteWriter(str(db), USER)
    assert writer.list_skips(COLLECTION) == [{"start": 10, "end": 80}]
    assert writer.list_skips("nope") == []
