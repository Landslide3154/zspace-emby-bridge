"""写极影视数据库：进度、建档与已看。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.native import LocalSqliteWriter, parse_item_id

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
    video_duration integer
);
CREATE UNIQUE INDEX user_playlist ON zvideo_playlist (user_name, classification_id, collection_id);
CREATE TABLE zvideo_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name varchar,
    video_id varchar,
    collection_id varchar,
    name varchar,
    path varchar,
    duration integer,
    state tinyint default 1,
    updated_at datetime
);
"""

USER = "17611545258"
COLLECTION = "560a79a3e816b6e"
CLASSIFICATION = "484e30ab-18be-4c7a-a6dd-e7105cad7e48"
EMBY_ITEM = f"collection_{COLLECTION}_{CLASSIFICATION}"
NEW_COLLECTION = "aabbccddeeff00"
NEW_VIDEO = "0011223344aabbc"


def make_db(path: Path, position: int = 100) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO zvideo_list (user_name, video_id, collection_id, name, path, duration, state)"
        " VALUES (?,?,?,?,?,?,?)",
        (USER, "7d2002151cff985", COLLECTION, "后室.mkv", "/media/a.mkv", 6636, 1),
    )
    conn.execute(
        "INSERT INTO zvideo_list (user_name, video_id, collection_id, name, path, duration, state)"
        " VALUES (?,?,?,?,?,?,?)",
        (USER, NEW_VIDEO, NEW_COLLECTION, "新片.mkv", "/media/new.mkv", 5400, 1),
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


def test_parse_item_id() -> None:
    assert parse_item_id(EMBY_ITEM) == (COLLECTION, CLASSIFICATION)
    assert parse_item_id("weird-id") is None
    assert parse_item_id("") is None


def test_updates_position_and_timestamp(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.write_position(COLLECTION, 1800)
    assert result.changed == 1
    row = sqlite3.connect(db).execute(
        "SELECT play_duration, updated_at FROM zvideo_playlist WHERE collection_id = ?", (COLLECTION,)
    ).fetchone()
    assert row[0] == 1800
    assert row[1] != "2026-10-26 12:00:00"


def test_inserts_row_for_item_never_played_in_jellyfin_app(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.write_position(NEW_COLLECTION, 300, classification_id=CLASSIFICATION)
    assert result.changed == 1
    row = sqlite3.connect(db).execute(
        "SELECT play_duration, video_id, duration_alias FROM (SELECT play_duration, video_id, video_duration AS"
        " duration_alias FROM zvideo_playlist WHERE collection_id = ?)",
        (NEW_COLLECTION,),
    ).fetchone()
    assert row == (300, NEW_VIDEO, 5400)


def test_writes_to_other_user_untouched(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), "someone-else")
    result = writer.write_position(COLLECTION, 1800)
    assert result.changed == 0
    assert result.reason in {"not_in_playlist", "not_in_library"}


def test_missing_item_is_reported_not_created(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.write_position("deadbeefcafe", 60)
    assert result.changed == 0
    assert result.reason == "not_in_playlist"


def test_rejects_unsafe_identifiers(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    with pytest.raises(ValueError):
        writer.write_position("x'; DROP TABLE zvideo_playlist; --", 10)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM zvideo_playlist").fetchone()[0] == 1


def test_negative_position_is_ignored(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.write_position(COLLECTION, -5)
    assert result.changed == 0
    assert result.reason == "invalid_position"


def test_insert_picks_one_row_when_collection_has_multiple_files(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO zvideo_list (user_name, video_id, collection_id, name, path, duration, state)"
        " VALUES (?,?,?,?,?,?,?)",
        (USER, "0022334455aabbc", NEW_COLLECTION, "新片 E02.mkv", "/media/new2.mkv", 5500, 1),
    )
    conn.commit()
    conn.close()
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.write_position(NEW_COLLECTION, 300, classification_id=CLASSIFICATION)
    assert result.changed == 1
    assert (
        sqlite3.connect(db)
        .execute("SELECT COUNT(*) FROM zvideo_playlist WHERE collection_id = ?", (NEW_COLLECTION,))
        .fetchone()[0]
        == 1
    )


def test_mark_played_sets_state_and_removes_from_continue_watching(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.mark_played(COLLECTION)
    assert result.changed == 1
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT state FROM zvideo_list WHERE collection_id = ?", (COLLECTION,)).fetchone()[0] == 2
    assert conn.execute(
        "SELECT COUNT(*) FROM zvideo_playlist WHERE collection_id = ?", (COLLECTION,)
    ).fetchone()[0] == 0


def test_mark_played_unknown_item(tmp_path: Path) -> None:
    db = make_db(tmp_path / "zvideo.db")
    writer = LocalSqliteWriter(str(db), USER)
    result = writer.mark_played("deadbeefcafe")
    assert result.changed == 0
    assert result.reason == "not_in_library"
