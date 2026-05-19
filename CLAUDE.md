# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`fast-resume-plus` (`fr`) — a TUI for searching and resuming sessions across multiple coding-agent CLIs (Claude Code, Codex, Copilot CLI, Copilot VS Code, Crush, Gemini, Kiro, OpenCode, Vibe). Sessions are normalized via per-agent adapters and indexed in a Tantivy full-text search index.

The package name is `fast-resume-plus` (PyPI) with entry-points `fr`, `fast-resume`, and `fast-resume-plus`. Requires Python `>=3.14`. Managed with `uv`.

## Common commands

```bash
uv sync                          # install deps (incl. dev group)
uv run fr                        # run the CLI from source
uv run pytest                    # run full test suite (pytest-xdist auto-parallel via pyproject)
uv run pytest tests/test_index.py::test_name -v   # run a single test
uv run pytest -n 0               # disable xdist (helpful for debugging)
uv run ruff check . && uv run ruff format .
uv run ty check src/             # type check (Astral's `ty`)
uv run pre-commit run --all-files
```

Pre-commit hooks run `ruff` (with `--fix`), `ruff-format`, `ty check src/`, and the full `pytest` suite on every commit — expect commits to take a few seconds.

Commit messages follow Conventional Commits (`feat`, `fix`, `chore`, etc.); `commitlint` enforces a 72-char header. `semantic-release` (`.releaserc.json`) cuts versions from `master` — do not hand-edit `pyproject.toml`'s `version` or `CHANGELOG.md`.

## Architecture

The README has a thorough architecture section with diagrams; below are the non-obvious points worth knowing before editing.

**Adapter contract** — `src/fast_resume/adapters/base.py` defines two layers:
- `AgentAdapter` (Protocol): the public interface every adapter implements (`find_sessions`, `find_sessions_incremental`, `get_resume_command`, `is_available`, `get_raw_stats`, `supports_yolo`).
- `BaseSessionAdapter` (ABC): template-method base for file-based adapters. Subclasses implement `_scan_session_files()` (returns `{session_id: (Path, mtime)}`) and `_parse_session_file()`; the base handles incremental scanning, mtime comparison, and deleted-ID detection.

Which adapters use which base:

| Adapter | Base | Data location | `supports_yolo` |
|---|---|---|---|
| Claude | `BaseSessionAdapter` | `~/.claude/projects/` (JSONL per session, skips `agent-*.jsonl`) | True |
| Codex | `BaseSessionAdapter` | `~/.codex/sessions/` (JSONL in `YYYY/MM/DD` subdirs) | True |
| Copilot CLI | `BaseSessionAdapter` | `~/.copilot/session-state/` (JSONL, also UUID subdirs) | True |
| Copilot VS Code | Protocol directly | `~/.config/Code/User/globalStorage/emptyWindowChatSessions/` + `workspaceStorage/*/chatSessions/` (JSON, platform path varies) | False |
| Crush | Protocol directly | `~/.local/share/crush/projects.json` → per-project `crush.db` (SQLite) | False |
| Gemini | `BaseSessionAdapter` | `~/.gemini/tmp/<slug>/chats/` (`.json` or `.jsonl`; deduped by `_scan_session_files`) | True |
| Kiro | `BaseSessionAdapter` | `~/.kiro/sessions/cli/` (`<uuid>.json` metadata + `<uuid>.jsonl` events) | True |
| OpenCode | Protocol directly | `~/.local/share/opencode/opencode.db` (SQLite, 1.2+) or `~/.local/share/opencode/storage/` (legacy JSON) | False |
| Vibe | `BaseSessionAdapter` | `~/.vibe/logs/session/session_*/` (per-session directories with `meta.json` + `messages.jsonl`) | True |

**Resume commands** (all returned as `argv` lists safe to `os.execvp`):
- Claude: `claude [--dangerously-skip-permissions] --resume <id>`
- Codex: `codex [--dangerously-bypass-approvals-and-sandbox] resume <id>`
- Copilot CLI: `copilot [--allow-all-tools --allow-all-paths] --resume <id>`
- Copilot VS Code: `code [<directory>]` (VS Code has no session-resume CLI flag)
- Crush: `crush` (no session ID arg; `cli.py` chdirs first, Crush shows its own session picker)
- Gemini: `gemini [--yolo] --resume <id>`
- Kiro: `kiro-cli chat [--trust-all-tools] --resume-id <id>`
- OpenCode: `opencode <directory> --session <id>`
- Vibe: `vibe [--agent auto-approve] --resume <id>`

Crush resume is blocked in the TUI (`action_resume_session` checks `session.agent == "crush"` and shows an error toast) because Crush has no CLI resume flag.

**Yolo auto-detect** — Codex sniffs `turn_context` events and checks whether `approval_policy` is `"never"` or `sandbox_policy.mode` is `"danger-full-access"`. Vibe reads `config.auto_approve` (or legacy `auto_approve`) from `meta.json`. Both set `Session.yolo = True` at parse time. Claude, Copilot CLI, Gemini, and Kiro have no yolo signal in their session files, so the TUI shows a modal when the user presses Enter on those sessions (unless `--yolo` was passed at startup, which skips the modal entirely).

**Incremental indexing** — `SessionSearch` (in `search.py`) loads `(session_id → (mtime, agent))` pairs from Tantivy, dispatches all adapters concurrently in a `ThreadPoolExecutor`, and streams sessions into the index via the `on_session` callback. `flush_pending()` snapshots the buffer under one lock, then commits under a separate `writer_lock` so adapter threads keep appending while Tantivy flushes. Adapters re-parse only files whose mtime exceeds the stored value by `MTIME_TOLERANCE` (1 ms).

Gemini's `_scan_session_files` deduplicates session IDs when both `.json` and `.jsonl` exist for the same session: it keeps whichever file has the later mtime. The JSONL parser applies `$set` patches only to known timestamp keys (`startTime`, `lastUpdated`) and de-dupes repeated message rows by ID.

Kiro's `_scan_session_files` uses the newer of the `.json` meta mtime and the `.jsonl` events mtime, so a still-running session triggers re-indexing even if only the event stream grew.

OpenCode's incremental path uses `json_extract` to filter rows in SQL rather than loading the full JSON payload into Python, which matters when the database holds thousands of messages.

**Schema versioning** — `config.SCHEMA_VERSION` is written to `~/.cache/fast-resume/tantivy_index/.schema_version`. Any change to the Tantivy schema in `index.py` requires bumping `SCHEMA_VERSION` or users get cryptic deserialization errors on upgrade. The index is auto-wiped and rebuilt on version mismatch. Current version: **21** (added Gemini + Kiro adapters).

**Resume handoff** — `cli.py` does not subprocess the agent. After `run_tui()` returns a `(resume_cmd, resume_dir)` tuple, it `os.chdir(resume_dir)` then `os.execvp()` to replace the Python process entirely. Before calling `exit()`, the TUI validates the binary is on PATH via `shutil.which` and shows an error toast if not — the TUI has already been torn down by the time `execvp` would raise `FileNotFoundError`.

**Query syntax** — `query.py` parses a keyword DSL from the search string before handing free-text to Tantivy:
- `agent:claude,codex` — include multiple agents (OR logic)
- `-agent:claude` or `agent:!claude` — exclude an agent
- `agent:claude,!codex` — mixed include/exclude
- `dir:my-project` — substring match on directory path
- `date:today`, `date:yesterday`, `date:week`, `date:month`
- `date:<1h`, `date:>2d` — relative time (units: `m`, `h`, `d`, `w`, `mo`, `y`)

Typed `agent:` keywords in the search box are bidirectionally synced with the filter bar buttons via `_syncing_filter` guard to prevent loops.

**TUI layout** — `src/fast_resume/tui/` is a Textual app split into `app.py` (orchestration), `results_table.py`, `search_input.py`, `preview.py`, `filter_bar.py`, `modal.py` (yolo prompt), `query.py` (autocomplete + agent sync helpers), `styles.py`, and `utils.py` (clipboard). Searches are debounced 50 ms; the preview pane jumps to and highlights the first matching term and memoizes the last rendered session to avoid per-keystroke repaints during `j`/`k` navigation.

**Yolo modal** — `YoloModeModal` dismisses with `None` (cancel), `False` (launch without yolo), or `True` (launch with yolo). The checkbox is excluded from Tab focus cycling (`can_focus = False` on mount) so Enter can't accidentally toggle it; `space`/`y`/`n` still flip it. The `c` keybinding (copy resume command) guards against stacking a second modal if pressed while the first is already open.

**What gets indexed** — only user prompts and assistant text responses. Tool calls, tool results, system/meta messages, and slash-command outputs are excluded.

## Tests

- `pytest-asyncio` is in `asyncio_mode = "auto"` — don't decorate async tests with `@pytest.mark.asyncio`.
- `pytest-xdist` runs `-n auto` by default; tests must be isolation-safe. Use `tmp_path` rather than fixed paths, and never touch the user's real `~/.cache/fast-resume/` from tests.
- TUI tests use Textual's `App.run_test()` pattern; see `tests/test_tui.py` for examples.
- Each adapter has its own `test_<agent>_adapter.py` — when adding an adapter, mirror the structure (fixtures with sample session files, mtime/incremental cases, resume-command assertions including yolo variants).
- Current test files: `test_claude_adapter.py`, `test_codex_adapter.py`, `test_copilot_adapter.py`, `test_copilot_vscode_adapter.py`, `test_crush_adapter.py`, `test_gemini_adapter.py`, `test_kiro_adapter.py`, `test_opencode_adapter.py`, `test_vibe_adapter.py`, `test_index.py`, `test_search.py`, `test_query.py`, `test_tui.py`, `test_cli.py`, `test_integration.py`, `test_error_handling.py`.
