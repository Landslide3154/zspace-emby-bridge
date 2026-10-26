"""进度存储：WAL、重启不丢、按 token 哈希隔离。"""
from __future__ import annotations

from pathlib import Path

from app.proxy import ProgressEvent
from app.store import ProgressStore, token_hash


def _event(ticks: int | None, path: str = "/emby/Sessions/Playing/Progress") -> ProgressEvent:
    return ProgressEvent(
        method="POST",
        path=path,
        item_id="i1",
        position_ticks=ticks,
        play_session_id="ps",
        has_position_ticks=ticks is not None,
        body_format="json",
        body_summary="",
        received_at=1_792_991_725.0,
    )


def test_token_hash_hides_raw_token() -> None:
    hashed = token_hash("secret-token")
    assert "secret-token" not in hashed
    assert hashed == token_hash("secret-token")
    assert hashed != token_hash("secret-token2")
    assert len(hashed) == 32


def test_upsert_get_and_reopen(tmp_path: Path) -> None:
    db = str(tmp_path / "progress.db")
    store = ProgressStore(db)
    store.record(_event(6000000000), token_hash("t1"), user_id="u1")
    assert store.get(token_hash("t1"), "i1").position_ticks == 6000000000
    store.close()

    reopened = ProgressStore(db)  # 模拟容器重启
    record = reopened.get(token_hash("t1"), "i1")
    assert record is not None
    assert record.position_ticks == 6000000000
    reopened.close()


def test_wal_mode_enabled(tmp_path: Path) -> None:
    store = ProgressStore(str(tmp_path / "p.db"))
    assert store.journal_mode().lower() == "wal"
    store.close()


def test_tokens_isolated(tmp_path: Path) -> None:
    store = ProgressStore(str(tmp_path / "p.db"))
    store.record(_event(100), token_hash("a"), user_id="u1")
    store.record(_event(200), token_hash("b"), user_id="u1")
    assert store.get(token_hash("a"), "i1").position_ticks == 100
    assert store.get(token_hash("b"), "i1").position_ticks == 200
    assert store.get(token_hash("c"), "i1") is None
    store.close()


def test_stopped_at_zero_does_not_wipe_progress(tmp_path: Path) -> None:
    store = ProgressStore(str(tmp_path / "p.db"))
    store.record(_event(6000000000), token_hash("t"), user_id="u1")
    store.record(_event(0, "/emby/Sessions/Playing/Stopped"), token_hash("t"), user_id="u1")
    assert store.get(token_hash("t"), "i1").position_ticks == 6000000000
    store.close()


def test_missing_ticks_is_ignored(tmp_path: Path) -> None:
    store = ProgressStore(str(tmp_path / "p.db"))
    store.record(_event(None, "/emby/Sessions/Playing/Stopped"), token_hash("t"), user_id="u1")
    assert store.get(token_hash("t"), "i1") is None
    store.close()


def test_recent_newest_first(tmp_path: Path) -> None:
    store = ProgressStore(str(tmp_path / "p.db"))
    store.record(_event(10000000), token_hash("t"), user_id="u1")
    store.record(_event(20000000), token_hash("t"), user_id="u1")
    entries = store.recent(5)
    assert entries[0]["item_id"] == "i1"
    assert entries[0]["position_ticks"] == 20000000
    store.close()
