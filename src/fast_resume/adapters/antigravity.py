"""Google Antigravity CLI (`agy`) session adapter.

Antigravity is Google's announced successor to the Gemini CLI. The two
binaries coexist in `~/.gemini/` but in different subdirectories, so this
adapter lives alongside `GeminiAdapter` rather than replacing it.

Storage layout (verified on a real system):

    ~/.gemini/antigravity-cli/conversations/<uuid>.pb
        One file per conversation. The filename (UUID) is the session id.
        The file payload is encrypted at rest (entropy 8.00, all 256 byte
        values present, no compression magic), so we cannot parse content
        out of it — only existence + filename + mtime.

    ~/.gemini/antigravity-cli/history.jsonl
        Plain JSONL, append-only. Each row records a user prompt:

            {"display": "...", "timestamp": <ms>,
             "workspace": "/abs/path", "conversationId": "<uuid>"}

        Early rows from before agy assigned a conversation id are missing
        the `conversationId` field and are skipped.

Because the conversation blobs are encrypted, only user prompts are
indexable. Assistant responses are not available.
"""

import re

import orjson
from datetime import datetime
from pathlib import Path

from ..config import AGENTS, ANTIGRAVITY_CONVERSATIONS_DIR, ANTIGRAVITY_HISTORY_FILE
from ..logging_config import log_parse_error
from .base import (
    BaseSessionAdapter,
    ErrorCallback,
    ParseError,
    RawAdapterStats,
    Session,
    truncate_title,
)

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


class AntigravityAdapter(BaseSessionAdapter):
    """Adapter for Google Antigravity CLI (`agy`) sessions."""

    name = "agy"
    color = AGENTS["agy"]["color"]
    badge = AGENTS["agy"]["badge"]
    supports_yolo = True

    def __init__(
        self,
        conversations_dir: Path | None = None,
        history_file: Path | None = None,
    ) -> None:
        self._conversations_dir = (
            conversations_dir
            if conversations_dir is not None
            else ANTIGRAVITY_CONVERSATIONS_DIR
        )
        self._history_file = (
            history_file if history_file is not None else ANTIGRAVITY_HISTORY_FILE
        )
        # `_sessions_dir` is required by `BaseSessionAdapter` for
        # `get_raw_stats` defaults; we override `get_raw_stats` below but
        # still wire this so any base-class path that touches it stays
        # consistent.
        self._sessions_dir = self._conversations_dir

        # Cache of (history mtime -> {conversation_id -> [rows]}) so we
        # parse the (potentially large) history.jsonl at most once per
        # scan. Invalidated by mtime change.
        self._history_cache_mtime: float | None = None
        self._history_cache: dict[str, list[dict]] = {}

    def is_available(self) -> bool:
        return self._conversations_dir.exists() and self._conversations_dir.is_dir()

    def find_sessions(self) -> list[Session]:
        """Find all Antigravity conversations."""
        if not self.is_available():
            return []
        sessions: list[Session] = []
        # Reset history cache once at the start so a single scan reads
        # history.jsonl at most once.
        self._reset_history_cache()
        for _session_id, (path, _mtime) in self._scan_session_files().items():
            session = self._parse_session_file(path)
            if session:
                sessions.append(session)
        return sessions

    def find_sessions_incremental(
        self,
        known: dict[str, tuple[float, str]],
        on_error: ErrorCallback = None,
        on_session=None,
    ) -> tuple[list[Session], list[str]]:
        """Run incremental scan with the per-scan history cache reset."""
        # Reset history cache once per incremental scan; the base class
        # may re-parse many .pb files but they all share one history.jsonl.
        self._reset_history_cache()
        return super().find_sessions_incremental(
            known, on_error=on_error, on_session=on_session
        )

    def _reset_history_cache(self) -> None:
        self._history_cache_mtime = None
        self._history_cache = {}

    def _scan_session_files(self) -> dict[str, tuple[Path, float]]:
        """Return `{session_id: (.pb path, max(.pb mtime, history mtime))}`.

        The `.pb` mtime alone misses the case where the user typed a new
        prompt that got appended to `history.jsonl` without (yet) altering
        the encrypted blob, so we fold the history file's mtime into the
        comparison value. This guarantees an incremental scan re-parses
        the affected conversation when either file changes.
        """
        current: dict[str, tuple[Path, float]] = {}
        try:
            history_mtime = self._history_file.stat().st_mtime
        except OSError:
            history_mtime = 0.0

        try:
            entries = list(self._conversations_dir.glob("*.pb"))
        except OSError:
            return current

        for pb_file in entries:
            try:
                pb_mtime = pb_file.stat().st_mtime
            except OSError:
                continue
            session_id = pb_file.stem
            mtime = max(pb_mtime, history_mtime)
            current[session_id] = (pb_file, mtime)
        return current

    def _parse_session_file(
        self, session_file: Path, on_error: ErrorCallback = None
    ) -> Session | None:
        """Parse a single Antigravity conversation given its `.pb` path."""
        pb_path = session_file
        session_id = pb_path.stem
        rows = self._rows_for(session_id, pb_path=pb_path, on_error=on_error)

        if not rows:
            return self._fallback_session(session_id, pb_path, on_error)

        title, directory, content, max_ts_ms = self._aggregate_rows(rows)
        if max_ts_ms > 0:
            timestamp = datetime.fromtimestamp(max_ts_ms / 1000)
        else:
            timestamp = self._pb_timestamp(pb_path, on_error)
            if timestamp is None:
                return None

        return Session(
            id=session_id,
            agent=self.name,
            title=title,
            directory=directory,
            timestamp=timestamp,
            content=content,
            message_count=len(rows),
        )

    def _fallback_session(
        self, session_id: str, pb_path: Path, on_error: ErrorCallback
    ) -> Session | None:
        """Build a content-less Session for a `.pb` with no history rows.

        Conversation exists but has no recorded user prompts (early rows
        lacked `conversationId`, or it was created via some path that
        doesn't write to history.jsonl). Still emit a row so the
        conversation is searchable / resumable by id.
        """
        timestamp = self._pb_timestamp(pb_path, on_error)
        if timestamp is None:
            return None
        return Session(
            id=session_id,
            agent=self.name,
            title="Untitled conversation",
            directory="",
            timestamp=timestamp,
            content="",
            message_count=0,
        )

    def _aggregate_rows(self, rows: list[dict]) -> tuple[str, str, str, int]:
        """Aggregate history rows for a single conversation.

        Returns ``(title, directory, content, max_ts_ms)``. User prompts only —
        assistant text is encrypted and unrecoverable.
        """
        first_row = rows[0]
        first_prompt = str(first_row.get("display") or "").strip()
        directory = str(first_row.get("workspace") or "")
        title = (
            truncate_title(first_prompt, max_length=100, word_break=False)
            if first_prompt
            else "Untitled conversation"
        )

        content_parts: list[str] = []
        max_ts_ms = 0
        for row in rows:
            text = str(row.get("display") or "").strip()
            if text:
                content_parts.append(f"» {text}")
            ts_val = row.get("timestamp")
            if isinstance(ts_val, int) and ts_val > max_ts_ms:
                max_ts_ms = ts_val

        return title, directory, "\n\n".join(content_parts), max_ts_ms

    def _pb_timestamp(self, pb_path: Path, on_error: ErrorCallback) -> datetime | None:
        """Stat the .pb file for its mtime; report and return None on OSError."""
        try:
            return datetime.fromtimestamp(pb_path.stat().st_mtime)
        except OSError as e:
            self._report(on_error, str(pb_path), "OSError", str(e))
            return None

    def _rows_for(
        self,
        session_id: str,
        pb_path: Path,
        on_error: ErrorCallback = None,
    ) -> list[dict]:
        """Return all `history.jsonl` rows tagged with `session_id`.

        Reads (and caches) the full history file once per scan. Rows
        missing `conversationId` are silently skipped (early agy rows
        predate that field). Malformed JSON lines are reported via
        `on_error` and skipped.
        """
        self._ensure_history_loaded(on_error=on_error)
        return list(self._history_cache.get(session_id, ()))

    def _ensure_history_loaded(self, on_error: ErrorCallback = None) -> None:
        if not self._history_file.exists():
            self._reset_history_cache()
            return
        try:
            mtime = self._history_file.stat().st_mtime
        except OSError as e:
            self._report(on_error, str(self._history_file), "OSError", str(e))
            self._reset_history_cache()
            return

        if self._history_cache_mtime == mtime:
            return

        rows_by_conv: dict[str, list[dict]] = {}
        try:
            with open(self._history_file, "rb") as f:
                for line in f:
                    parsed = self._parse_history_line(line, on_error)
                    if parsed is None:
                        continue
                    conv_id, entry = parsed
                    rows_by_conv.setdefault(conv_id, []).append(entry)
        except OSError as e:
            self._report(on_error, str(self._history_file), "OSError", str(e))
            self._reset_history_cache()
            return

        self._history_cache_mtime = mtime
        self._history_cache = rows_by_conv

    def _parse_history_line(
        self, line: bytes, on_error: ErrorCallback
    ) -> tuple[str, dict] | None:
        """Decode one `history.jsonl` line; return ``(conv_id, entry)`` or None.

        Returns None for blank lines, malformed JSON (reported via on_error),
        non-dict payloads, and rows missing a usable `conversationId`.
        """
        line = line.strip()
        if not line:
            return None
        try:
            entry = orjson.loads(line)
        except orjson.JSONDecodeError as e:
            self._report(on_error, str(self._history_file), "JSONDecodeError", str(e))
            return None
        if not isinstance(entry, dict):
            return None
        conv_id = entry.get("conversationId")
        if not isinstance(conv_id, str) or not conv_id:
            return None
        return conv_id, entry

    def _report(
        self,
        on_error: ErrorCallback,
        file_path: str,
        error_type: str,
        message: str,
    ) -> None:
        error = ParseError(
            agent=self.name,
            file_path=file_path,
            error_type=error_type,
            message=message,
        )
        log_parse_error(error.agent, error.file_path, error.error_type, error.message)
        if on_error:
            on_error(error)

    def get_resume_command(self, session: Session, yolo: bool = False) -> list[str]:
        """Get command to resume an Antigravity conversation.

        Antigravity conversation ids are always UUIDs (the .pb filename
        is the id), so we validate against the same regex used in the
        Codex adapter to block argv injection via a tampered file name.
        """
        if not _UUID_RE.fullmatch(session.id):
            raise ValueError(
                f"Refusing to resume agy session with non-UUID id: {session.id!r}"
            )
        cmd = ["agy"]
        if yolo:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--conversation", session.id])
        return cmd

    def get_raw_stats(self) -> RawAdapterStats:
        if not self.is_available():
            return RawAdapterStats(
                agent=self.name,
                data_dir=str(self._conversations_dir),
                available=False,
                file_count=0,
                total_bytes=0,
            )

        files = self._scan_session_files()
        total_bytes = 0
        for path, _ in files.values():
            try:
                total_bytes += path.stat().st_size
            except OSError:
                pass
        return RawAdapterStats(
            agent=self.name,
            data_dir=str(self._conversations_dir),
            available=True,
            file_count=len(files),
            total_bytes=total_bytes,
        )
