"""Tests for the Antigravity CLI (`agy`) session adapter."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from fast_resume.adapters.antigravity import AntigravityAdapter
from fast_resume.adapters.base import Session

UUID_A = "60766a71-92cb-4f73-b977-928593adcbf5"
UUID_B = "11111111-2222-3333-4444-555555555555"
UUID_C = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def antigravity_dirs(temp_dir: Path):
    """Return (conversations_dir, history_file) inside a fresh temp tree."""
    conversations = temp_dir / "conversations"
    conversations.mkdir()
    history = temp_dir / "history.jsonl"
    return conversations, history


@pytest.fixture
def adapter(antigravity_dirs):
    conversations, history = antigravity_dirs
    return AntigravityAdapter(conversations_dir=conversations, history_file=history)


def _write_pb(conversations_dir: Path, uuid: str, mtime: float | None = None) -> Path:
    path = conversations_dir / f"{uuid}.pb"
    # Use opaque bytes so a future code reader knows we intentionally
    # don't parse this file.
    path.write_bytes(b"\x00\xff\x01\xfe" * 16)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _write_history(history_file: Path, rows: list[dict]) -> None:
    with open(history_file, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class TestAntigravityAdapter:
    def test_name_and_attributes(self, adapter):
        assert adapter.name == "agy"
        assert adapter.color is not None
        assert adapter.badge == "agy"
        assert adapter.supports_yolo is True

    def test_is_available_false_when_dir_missing(self, temp_dir):
        a = AntigravityAdapter(
            conversations_dir=temp_dir / "does-not-exist",
            history_file=temp_dir / "history.jsonl",
        )
        assert a.is_available() is False

    def test_is_available_false_when_path_is_file(self, temp_dir):
        # Path exists but isn't a directory — adapter must treat it as
        # unavailable rather than crashing on the first glob().
        fake = temp_dir / "not-a-dir"
        fake.write_text("nope")
        a = AntigravityAdapter(
            conversations_dir=fake,
            history_file=temp_dir / "history.jsonl",
        )
        assert a.is_available() is False

    def test_pb_without_history_rows_yields_fallback_session(
        self, adapter, antigravity_dirs
    ):
        conversations, _history = antigravity_dirs
        pb_path = _write_pb(conversations, UUID_A)

        session = adapter._parse_session_file(pb_path)

        assert session is not None
        assert session.id == UUID_A
        assert session.agent == "agy"
        assert session.title == "Untitled conversation"
        assert session.directory == ""
        assert session.content == ""
        assert session.message_count == 0
        # Timestamp falls back to file mtime — must be a datetime.
        assert isinstance(session.timestamp, datetime)

    def test_pb_with_matching_history_rows(self, adapter, antigravity_dirs):
        conversations, history = antigravity_dirs
        _write_pb(conversations, UUID_A)
        _write_history(
            history,
            [
                {
                    "display": "first prompt",
                    "timestamp": 1779296700000,
                    "workspace": "/home/cody/tmp",
                    "conversationId": UUID_A,
                },
                {
                    "display": "second prompt",
                    "timestamp": 1779296800000,
                    "workspace": "/home/cody/tmp",
                    "conversationId": UUID_A,
                },
                # Unrelated row for another conversation.
                {
                    "display": "elsewhere",
                    "timestamp": 1779296900000,
                    "workspace": "/elsewhere",
                    "conversationId": UUID_B,
                },
            ],
        )

        sessions = adapter.find_sessions()
        assert len(sessions) == 1
        session = sessions[0]

        assert session.id == UUID_A
        assert session.title == "first prompt"
        assert session.directory == "/home/cody/tmp"
        assert "» first prompt" in session.content
        assert "» second prompt" in session.content
        assert session.message_count == 2
        # max(timestamp) wins, converted from ms.
        assert session.timestamp == datetime.fromtimestamp(1779296800000 / 1000)

    def test_rows_missing_conversation_id_are_skipped(self, adapter, antigravity_dirs):
        conversations, history = antigravity_dirs
        _write_pb(conversations, UUID_A)
        _write_history(
            history,
            [
                # Pre-assignment row that agy emits before allocating an id.
                {
                    "display": "orphan",
                    "timestamp": 1779296700000,
                    "workspace": "/home/cody/tmp",
                },
                {
                    "display": "real prompt",
                    "timestamp": 1779296800000,
                    "workspace": "/home/cody/tmp",
                    "conversationId": UUID_A,
                },
            ],
        )

        sessions = adapter.find_sessions()
        assert len(sessions) == 1
        assert sessions[0].title == "real prompt"
        assert "orphan" not in sessions[0].content

    def test_malformed_history_line_logs_and_continues(self, adapter, antigravity_dirs):
        conversations, history = antigravity_dirs
        _write_pb(conversations, UUID_A)
        # Mix one good row, one malformed line, one more good row.
        with open(history, "w") as f:
            f.write(
                json.dumps(
                    {
                        "display": "before",
                        "timestamp": 1779296700000,
                        "workspace": "/w",
                        "conversationId": UUID_A,
                    }
                )
                + "\n"
            )
            f.write("not-json\n")
            f.write(
                json.dumps(
                    {
                        "display": "after",
                        "timestamp": 1779296800000,
                        "workspace": "/w",
                        "conversationId": UUID_A,
                    }
                )
                + "\n"
            )

        errors = []
        adapter._reset_history_cache()
        adapter._ensure_history_loaded(on_error=errors.append)

        # Now parse the conversation and check both rows survived.
        pb_path = conversations / f"{UUID_A}.pb"
        session = adapter._parse_session_file(pb_path)

        assert session is not None
        assert "» before" in session.content
        assert "» after" in session.content
        assert any(e.error_type == "JSONDecodeError" for e in errors)

    def test_pb_with_no_matching_rows_in_populated_history(
        self, adapter, antigravity_dirs
    ):
        # `.pb` for UUID_C exists but history.jsonl only contains rows
        # tagged for a different conversation. The .pb must still be
        # discoverable as a fallback session (so it remains resumable).
        conversations, history = antigravity_dirs
        _write_pb(conversations, UUID_C)
        _write_history(
            history,
            [
                {
                    "display": "for someone else",
                    "timestamp": 1779296700000,
                    "workspace": "/w",
                    "conversationId": UUID_A,
                },
            ],
        )

        sessions = adapter.find_sessions()
        assert len(sessions) == 1
        assert sessions[0].id == UUID_C
        assert sessions[0].title == "Untitled conversation"
        assert sessions[0].content == ""

    def test_get_resume_command_uuid(self, adapter):
        session = Session(
            id=UUID_A,
            agent="agy",
            title="t",
            directory="/x",
            timestamp=datetime.now(),
            content="",
        )
        assert adapter.get_resume_command(session) == [
            "agy",
            "--conversation",
            UUID_A,
        ]

    def test_get_resume_command_yolo(self, adapter):
        session = Session(
            id=UUID_A,
            agent="agy",
            title="t",
            directory="/x",
            timestamp=datetime.now(),
            content="",
        )
        assert adapter.get_resume_command(session, yolo=True) == [
            "agy",
            "--dangerously-skip-permissions",
            "--conversation",
            UUID_A,
        ]

    def test_get_resume_command_rejects_non_uuid(self, adapter):
        session = Session(
            id="not-a-uuid --evil-flag",
            agent="agy",
            title="t",
            directory="/x",
            timestamp=datetime.now(),
            content="",
        )
        with pytest.raises(ValueError):
            adapter.get_resume_command(session)

    def test_scan_uses_max_of_pb_and_history_mtime(self, adapter, antigravity_dirs):
        conversations, history = antigravity_dirs
        _write_pb(conversations, UUID_A, mtime=time.time() - 100)
        # Make history newer than the .pb so the max() call must pick it.
        history.write_text(
            json.dumps(
                {
                    "display": "x",
                    "timestamp": 1,
                    "workspace": "/w",
                    "conversationId": UUID_A,
                }
            )
            + "\n"
        )
        future = time.time() + 100
        os.utime(history, (future, future))

        files = adapter._scan_session_files()
        assert UUID_A in files
        _, mtime = files[UUID_A]
        assert mtime == pytest.approx(future, abs=1)

    def test_incremental_picks_up_history_only_change(self, adapter, antigravity_dirs):
        conversations, history = antigravity_dirs
        pb_path = _write_pb(conversations, UUID_A, mtime=time.time() - 100)
        # Snapshot the "known" baseline before any history exists.
        baseline_mtime = pb_path.stat().st_mtime
        known: dict[str, tuple[float, str]] = {UUID_A: (baseline_mtime, "agy")}

        # No history yet — nothing newer, so no re-parse.
        new_or_modified, deleted = adapter.find_sessions_incremental(known)
        assert new_or_modified == []
        assert deleted == []

        # Append to history.jsonl with a future mtime; .pb is unchanged.
        _write_history(
            history,
            [
                {
                    "display": "new prompt",
                    "timestamp": 1779296800000,
                    "workspace": "/w",
                    "conversationId": UUID_A,
                }
            ],
        )
        future = time.time() + 200
        os.utime(history, (future, future))

        new_or_modified, deleted = adapter.find_sessions_incremental(known)
        assert deleted == []
        assert len(new_or_modified) == 1
        assert new_or_modified[0].title == "new prompt"

    def test_incremental_skips_when_both_files_unchanged(
        self, adapter, antigravity_dirs
    ):
        conversations, history = antigravity_dirs
        pb_path = _write_pb(conversations, UUID_A, mtime=time.time() - 100)
        _write_history(
            history,
            [
                {
                    "display": "prompt",
                    "timestamp": 1779296700000,
                    "workspace": "/w",
                    "conversationId": UUID_A,
                }
            ],
        )
        past = time.time() - 100
        os.utime(history, (past, past))

        # baseline = max(.pb mtime, history mtime); use that as `known`.
        baseline_mtime = max(pb_path.stat().st_mtime, history.stat().st_mtime)
        known: dict[str, tuple[float, str]] = {UUID_A: (baseline_mtime, "agy")}

        new_or_modified, deleted = adapter.find_sessions_incremental(known)
        assert new_or_modified == []
        assert deleted == []

    def test_find_sessions_returns_empty_when_unavailable(self, adapter):
        with patch.object(adapter, "is_available", return_value=False):
            assert adapter.find_sessions() == []

    def test_get_raw_stats_unavailable(self, temp_dir):
        a = AntigravityAdapter(
            conversations_dir=temp_dir / "missing",
            history_file=temp_dir / "history.jsonl",
        )
        stats = a.get_raw_stats()
        assert stats.available is False
        assert stats.file_count == 0
        assert stats.total_bytes == 0

    def test_get_raw_stats_counts_files(self, adapter, antigravity_dirs):
        conversations, _history = antigravity_dirs
        _write_pb(conversations, UUID_A)
        _write_pb(conversations, UUID_B)

        stats = adapter.get_raw_stats()
        assert stats.available is True
        assert stats.file_count == 2
        assert stats.total_bytes > 0

    def test_truncates_long_title(self, adapter, antigravity_dirs):
        conversations, history = antigravity_dirs
        _write_pb(conversations, UUID_A)
        long_prompt = "x" * 300
        _write_history(
            history,
            [
                {
                    "display": long_prompt,
                    "timestamp": 1779296700000,
                    "workspace": "/w",
                    "conversationId": UUID_A,
                }
            ],
        )

        session = adapter.find_sessions()[0]
        assert session.title.endswith("...")
        assert len(session.title) <= 103
