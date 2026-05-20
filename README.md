<p align="center">
  <img src="assets/logo.png" alt="fast-resume" width="120" height="120">
</p>

# fast-resume-plus

[![CI](https://github.com/lusky3/fast-resume-plus/actions/workflows/workflow.yml/badge.svg)](https://github.com/lusky3/fast-resume-plus/actions/workflows/workflow.yml)
[![PyPI version](https://img.shields.io/pypi/v/fast-resume-plus)](https://pypi.org/project/fast-resume-plus/)
[![PyPI downloads](https://img.shields.io/pypi/dm/fast-resume-plus)](https://pypi.org/project/fast-resume-plus/)
[![codecov](https://codecov.io/github/lusky3/fast-resume-plus/graph/badge.svg?token=dB6NhLDkXA)](https://codecov.io/github/lusky3/fast-resume-plus)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=lusky3_fast-resume-plus&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=lusky3_fast-resume-plus)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=lusky3_fast-resume-plus&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=lusky3_fast-resume-plus)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=lusky3_fast-resume-plus&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=lusky3_fast-resume-plus)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=lusky3_fast-resume-plus&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=lusky3_fast-resume-plus)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/ba8380d1023148d2b0cfce4bd10ca074)](https://app.codacy.com/gh/lusky3/fast-resume-plus/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)

Search and resume conversations across Claude Code, Codex, Copilot, Gemini, Antigravity, Kiro, OpenCode, Vibe, and Crush — all from one place.

`fast-resume-plus` is a fork of [angristan/fast-resume](https://github.com/angristan/fast-resume) that adds Gemini CLI and Kiro adapters, and improves the launch modal.

![demo](https://github.com/user-attachments/assets/5ea9c2a5-a7c0-41bf-9357-394aeaaa0a06)

## Why fast-resume-plus?

Coding agents do have a resume feature, but either they don't support searching, or search is limited to titles. `fast-resume-plus` indexes the full conversation text across every agent you use, so you can search by what was actually discussed, then press Enter to resume directly.

## Features

- **Unified search**: One search box for sessions across all supported agents
- **Full-text search**: Searches user messages and assistant responses, not just titles
- **Tantivy-powered**: Search engine written in Rust, accessed via Python bindings. Fuzzy queries over thousands of sessions return in under 10 ms
- **Fuzzy matching**: Edit distance 1 typo tolerance with exact hits ranked higher
- **Direct resume**: Select a session and press Enter; `fr` `os.execvp`s the agent's CLI and exits
- **Incremental indexing**: Only re-parses files whose mtime changed; warm start is ~50 ms
- **TUI with preview pane**: Agent-colored results table, live preview of conversation content
- **Keyword filter DSL**: `agent:`, `dir:`, `date:` filters in the search box
- **Update notifications**: Checks PyPI for new releases on startup (disable with `--no-version-check`)

## Supported Agents

| Agent          | Session Location                                                   | Resume Command                                  | Yolo flag                                               | Auto-detect yolo |
| -------------- | ------------------------------------------------------------------ | ----------------------------------------------- | ------------------------------------------------------- | ---------------- |
| Claude Code    | `~/.claude/projects/<project>/*.jsonl`                             | `claude --resume <id>`                          | `--dangerously-skip-permissions`                        | No               |
| Codex CLI      | `~/.codex/sessions/**/*.jsonl`                                     | `codex resume <id>`                             | `--dangerously-bypass-approvals-and-sandbox`            | Yes              |
| Copilot CLI    | `~/.copilot/session-state/**/*.jsonl`                              | `copilot --resume <id>`                         | `--allow-all-tools --allow-all-paths`                   | No               |
| Copilot VS Code | `<VS Code storage>/workspaceStorage/*/chatSessions/*.json`        | `code <directory>`                              | _(n/a)_                                                 | No               |
| Gemini CLI     | `~/.gemini/tmp/<slug>/chats/session-*.json[l]`                     | `gemini --resume <id>`                          | `--yolo`                                                | No               |
| Antigravity CLI | `~/.gemini/antigravity-cli/conversations/<uuid>.pb` (+ history.jsonl)  | `agy --conversation <id>`                       | `--dangerously-skip-permissions`                        | No               |
| Kiro CLI       | `~/.kiro/sessions/cli/<uuid>.json` + `<uuid>.jsonl`                | `kiro-cli chat --resume-id <id>`                | `--trust-all-tools`                                     | No               |
| OpenCode       | `~/.local/share/opencode/opencode.db` (or legacy split JSON)       | `opencode <dir> --session <id>`                 | _(not supported)_                                       | No               |
| Vibe           | `~/.vibe/logs/session/session_*/`                                  | `vibe --resume <id>`                            | `--agent auto-approve`                                  | Yes              |
| Crush          | SQLite `crush.db` per project (paths from `~/.local/share/crush/`) | `crush` (opens picker in session directory)     | _(not supported)_                                       | No               |

**Yolo auto-detection**: Codex and Vibe store the permissions mode in their session files. Sessions originally started in yolo mode are automatically resumed in yolo mode.

**Launch modal**: For agents that support yolo but don't auto-detect it (Claude, Copilot CLI, Gemini, Antigravity, Kiro), pressing Enter shows a modal with a yolo checkbox. Press `Space`/`y`/`n` to toggle, then Enter to launch, or Esc to cancel. Pass `--yolo` to always skip the prompt.

**Antigravity caveat**: Antigravity (`agy`) is Google's announced successor to Gemini CLI. Because Antigravity encrypts conversation blobs at rest, only user prompts are indexable — assistant responses are not. The two CLIs coexist; fast-resume-plus will show both.

## Installation

### Recommended terminal

[Ghostty](https://ghostty.org/) is recommended. Other terminals may have issues displaying images in the preview pane.

### uv (PyPI)

```bash
# Run directly without installing
uvx --from fast-resume-plus fr

# Install permanently
uv tool install fast-resume-plus
fr
```

### pip

```bash
pip install fast-resume-plus
fr
```

Requires Python 3.14 or later.

## Usage

### Interactive TUI

```bash
# Open with all sessions
fr

# Pre-fill the search query
fr "authentication bug"

# Filter by agent
fr -a claude
fr -a gemini

# Filter by directory
fr -d myproject

# Combine filters
fr -a claude -d backend "api error"
```

### Keyword search syntax

Type these directly in the search box:

```text
agent:claude               Filter by agent
agent:claude,codex         Multiple agents (OR)
-agent:vibe                Exclude agent
agent:claude,!codex        Include claude, exclude codex

dir:myproject              Filter by directory (substring match)
dir:backend,!test          Include backend, exclude test

date:today                 Sessions from today
date:yesterday             Sessions from yesterday
date:<1h                   Within the last hour
date:<2d                   Within the last 2 days
date:>1w                   Older than 1 week
date:week                  Within the last 7 days
date:month                 Within the last 30 days
```

Mix keyword filters with free text:

```text
agent:claude date:<1d api bug
dir:backend -agent:vibe auth
```

Type `agent:cl` and press `Tab` to autocomplete to `agent:claude`.

### Non-interactive modes

```bash
# List sessions in terminal without opening the TUI
fr --no-tui

# List sessions without offering to resume
fr --list

# Force rebuild the index from scratch
fr --rebuild

# Show usage statistics
fr --stats

# Disable the version check on startup
fr --no-version-check
```

### Full command reference

```
Usage: fr [OPTIONS] [QUERY]

Arguments:
  QUERY                    Search query (optional)

Options:
  -a, --agent [agy|claude|codex|copilot-cli|copilot-vscode|crush|gemini|kiro|opencode|vibe]
                           Filter by agent
  -d, --directory TEXT     Filter by directory (substring match)
  --no-tui                 Output list to stdout instead of TUI
  --list                   Just list sessions, don't resume
  --rebuild                Force rebuild the session index
  --stats                  Show index statistics
  --yolo                   Resume with auto-approve/skip-permissions flags
  --no-version-check       Disable checking for new versions
  --version                Show version
  --help                   Show this message and exit
```

The CLI is also available as `fast-resume` and `fast-resume-plus`.

## Keybindings

### Navigation

| Key                     | Action                             |
| ----------------------- | ---------------------------------- |
| `↑` / `↓`               | Move selection up/down             |
| `j` / `k`               | Move selection up/down (vim-style) |
| `Page Up` / `Page Down` | Move by 10 rows                    |
| `Enter`                 | Resume selected session            |
| `/`                     | Focus search input                 |

### Preview and actions

| Key          | Action                                |
| ------------ | ------------------------------------- |
| `Ctrl+\``    | Toggle preview pane                   |
| `+` / `-`    | Resize preview pane                   |
| `Tab`        | Accept autocomplete suggestion        |
| `c`          | Copy full resume command to clipboard |
| `Ctrl+P`     | Open command palette                  |
| `q` / `Esc`  | Quit                                  |

### Launch modal

| Key              | Action                                   |
| ---------------- | ---------------------------------------- |
| `Tab` / `←` `→`  | Move focus between Cancel and Launch     |
| `Space`          | Toggle yolo checkbox                     |
| `y`              | Turn yolo on                             |
| `n`              | Turn yolo off                            |
| `Enter`          | Launch (with the checkbox's yolo state)  |
| `Esc`            | Cancel (stay in the TUI)                 |

## Statistics dashboard

Run `fr --stats` to see analytics about your coding sessions:

```
Index Statistics

  Total sessions          751
  Total messages          13,799
  Avg messages/session    18.4
  Index size              15.5 MB
  Index location          ~/.cache/fast-resume/tantivy_index
  Date range              2023-11-15 to 2025-12-22

Data by Agent

┌────────────────┬───────┬──────────┬──────────┬──────────┬──────────┬─────────────┐
│ Agent          │ Files │     Disk │ Sessions │ Messages │  Content │ Data Dir    │
├────────────────┼───────┼──────────┼──────────┼──────────┼──────────┼─────────────┤
│ claude         │   477 │ 312.9 MB │      377 │   10,415 │   3.1 MB │ ~/.claude/… │
│ copilot-vscode │   191 │ 146.0 MB │      189 │      954 │   1.4 MB │ ~/Library/… │
│ codex          │   107 │  23.6 MB │       89 │      321 │ 890.6 kB │ ~/.codex/…  │
│ opencode       │  9275 │  46.3 MB │       72 │    1,912 │ 597.7 kB │ ~/.local/…  │
│ vibe           │    12 │ 858.2 kB │       12 │      138 │ 380.0 kB │ ~/.vibe/…   │
│ crush          │     3 │   1.0 MB │        7 │       44 │  15.2 kB │ ~/.local/…  │
│ copilot-cli    │     5 │ 417.1 kB │        5 │       15 │   6.9 kB │ ~/.copilot… │
└────────────────┴───────┴──────────┴──────────┴──────────┴──────────┴─────────────┘

Activity by Day

 Mon   ██████████              89
 ...

Top Directories

┌───────────────────────┬──────────┬──────────┐
│ Directory             │ Sessions │ Messages │
├───────────────────────┼──────────┼──────────┤
│ ~/git/openvpn-install │      234 │    5,597 │
│ ...                   │          │          │
└───────────────────────┴──────────┴──────────┘
```

## How it works

### Architecture

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                              SessionSearch                                 │
│  • Dispatches adapters in parallel (ThreadPoolExecutor)                    │
│  • Compares file mtimes to detect changes (incremental updates)            │
│  • Delegates search queries to Tantivy index                               │
└────────────────────────────────────────────────────────────────────────────┘
                   │                                       │
      ┌────────────┴────────────┐                          │
      ▼                         ▼                          ▼
┌──────────────────┐   ┌──────────────────────────────────────────────────────┐
│  TantivyIndex    │   │                     Adapters                         │
│                  │   │  claude · codex · copilot-cli · copilot-vscode       │
│ • Fuzzy search   │◄──│  crush · gemini · agy · kiro · opencode · vibe       │
│ • mtime tracking │   └──────────────────────────────────────────────────────┘
│                  │
│ ~/.cache/        │
│   fast-resume/   │
└──────────────────┘
```

### Session parsing

Each agent stores sessions differently. Adapters normalize them into a common `Session` structure:

| Agent          | Format                                               | Parsing strategy                                                                           |
| -------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Claude Code    | JSONL in `~/.claude/projects/<project>/*.jsonl`      | Stream line-by-line, extract `user`/`assistant` messages, skip `agent-*` subprocess files |
| Codex CLI      | JSONL in `~/.codex/sessions/**/*.jsonl`              | Extract from `session_meta`, `response_item`, and `event_msg` entries                     |
| Copilot CLI    | JSONL in `~/.copilot/session-state/**/*.jsonl`       | Extract `user.message` and `assistant.message` event types                                 |
| Copilot VSCode | JSON in VS Code's `workspaceStorage/*/chatSessions/` | Parse `requests` array with message text and response values                               |
| Gemini CLI     | JSON/JSONL in `~/.gemini/tmp/<slug>/chats/`          | Two coexisting formats: single-JSON and streaming JSONL; deduplicated by `sessionId`       |
| Antigravity CLI | `<uuid>.pb` (encrypted) + `history.jsonl` (plain) | Conversation blobs are encrypted at rest; user prompts come from the unencrypted history.jsonl sidecar joined by conversationId. Assistant responses are not indexable. |
| Kiro CLI       | `<uuid>.json` (metadata) + `<uuid>.jsonl` (events)  | Read metadata for session info, parse event stream for `Prompt`/`AssistantMessage` kinds  |
| OpenCode       | SQLite `opencode.db` (1.2+) or legacy split JSON     | SQL `json_extract` for text parts; legacy falls back to parallel file I/O                 |
| Vibe           | Per-session folders with `meta.json` + `messages.jsonl` | Read metadata for yolo state and title, stream messages file for content                |
| Crush          | SQLite `crush.db` per project                        | Query `sessions` and `messages` tables, parse JSON `parts` column                         |

**Normalized `Session` fields:**

```python
@dataclass
class Session:
    id: str              # Unique identifier (usually UUID or filename stem)
    agent: str           # e.g. "claude", "gemini", "kiro"
    title: str           # First user message (max 80–100 chars)
    directory: str       # Working directory where the session was created
    timestamp: datetime  # Last modified time
    content: str         # Full conversation text (» user, ␣␣ assistant)
    message_count: int   # User + assistant turns (tool results excluded)
    mtime: float         # File mtime for incremental update detection
    yolo: bool           # Session was started with auto-approve (Codex, Vibe only)
```

**What gets indexed**: user text messages and assistant text responses.

**What is excluded**: tool call results, tool use invocations, system prompts, context summaries, and local command outputs (slash commands like `/context`). This keeps the index focused on the actual conversation.

### Incremental indexing

To avoid re-parsing every file on each launch:

1. Load `(session_id → (mtime, agent))` pairs from the Tantivy index
2. Scan session files, compare mtimes against stored values
3. Re-parse only files where `current_mtime > known_mtime + 0.001` (1 ms tolerance)
4. Detect sessions present in the index but no longer on disk (deleted)
5. Apply changes atomically: delete removed sessions, upsert modified ones

Sessions stream into the index in batches and appear in the TUI progressively. OpenCode uses a `ThreadPoolExecutor` for its legacy JSON format (thousands of small files) and processes shorter sessions first for faster initial results.

**Schema versioning**: `~/.cache/fast-resume/tantivy_index/.schema_version` tracks the index schema. If it doesn't match the code's `SCHEMA_VERSION` constant, the index is wiped and rebuilt. The current version is 22.

### Search

[Tantivy](https://github.com/quickwit-oss/tantivy) is a Rust full-text search library used via [tantivy-py](https://github.com/quickwit-oss/tantivy-py).

Queries combine an exact BM25 query (boosted 5×) with per-term `fuzzy_term_query(distance=1, prefix=True)` on both `title` and `content` fields. Exact matches rank first while typos still match.

```
┌─────────────┐   50ms    ┌─────────────┐  background  ┌─────────────┐
│  Keystroke  │ ────────► │  Debounce   │ ───────────► │   Worker    │
└─────────────┘  timer    └─────────────┘   thread     └──────┬──────┘
                                                              │
                          ┌─────────────┐              ┌──────▼──────┐
                          │   Render    │ ◄─────────── │   Tantivy   │
                          │   Table     │   results    │    Query    │
                          └─────────────┘              └─────────────┘
```

### Resume handoff

When you press Enter, `fr` hands off to the agent's CLI using `os.execvp()`, which replaces the Python process entirely:

```python
os.chdir(resume_dir)
os.execvp(resume_cmd[0], resume_cmd)
```

This means no subprocess overhead, shell history shows the agent's command rather than `fr`, and the agent inherits the correct working directory. If `execvp` fails (e.g. the agent is not in `$PATH`), the error is printed and `fr` exits with code 1.

### Performance

- **Cold start** (empty index): ~2 s
- **Warm start** (no changes): ~50 ms
- **Search query**: <10 ms for 10k+ sessions

Factors: Tantivy handles queries in Rust; `orjson` parses JSON ~10× faster than the stdlib; all adapters run in a `ThreadPoolExecutor`; the 50 ms search debounce prevents wasted queries while typing; search runs on a background thread so the UI never blocks.

## Development

```bash
git clone https://github.com/lusky3/fast-resume-plus.git
cd fast-resume-plus
uv sync

# Run from source
uv run fr

# Install pre-commit hooks
uv run pre-commit install

# Run tests (parallel by default)
uv run pytest -v

# Run a single test
uv run pytest tests/test_index.py::test_name -v

# Run without parallelism (easier to debug)
uv run pytest -n 0

# Lint and format
uv run ruff check . && uv run ruff format .

# Type check
uv run ty check src/
```

Pre-commit hooks run `ruff` (with `--fix`), `ruff-format`, `ty check src/`, and the full `pytest` suite on every commit. Commits follow Conventional Commits (`feat`, `fix`, `chore`, etc.) and `commitlint` enforces a 72-character header limit. `semantic-release` cuts releases from `main`; do not hand-edit the version in `pyproject.toml` or `CHANGELOG.md`.

### Project structure

```text
fast-resume-plus/
├── src/fast_resume/
│   ├── cli.py              # Click CLI entry point
│   ├── config.py           # AGENTS dict, storage paths, SCHEMA_VERSION
│   ├── index.py            # TantivyIndex — search engine wrapper
│   ├── search.py           # SessionSearch — adapter orchestration
│   ├── query.py            # Keyword DSL parser (agent:, dir:, date:)
│   ├── assets/             # Agent icon PNGs
│   ├── tui/
│   │   ├── app.py          # FastResumeApp (Textual App subclass)
│   │   ├── filter_bar.py   # Agent filter buttons
│   │   ├── modal.py        # YoloModeModal (launch dialog)
│   │   ├── preview.py      # Session preview pane
│   │   ├── query.py        # Autocomplete / keyword highlighting
│   │   ├── results_table.py
│   │   ├── search_input.py
│   │   ├── styles.py
│   │   └── utils.py        # Clipboard helper
│   └── adapters/
│       ├── base.py         # Session dataclass, AgentAdapter protocol, BaseSessionAdapter ABC
│       ├── antigravity.py
│       ├── claude.py
│       ├── codex.py
│       ├── copilot.py
│       ├── copilot_vscode.py
│       ├── crush.py
│       ├── gemini.py
│       ├── kiro.py
│       ├── opencode.py
│       └── vibe.py
├── tests/
├── pyproject.toml
└── README.md
```

### Tech stack

| Component          | Library                                                             |
| ------------------ | ------------------------------------------------------------------- |
| TUI framework      | [Textual](https://textual.textualize.io/)                           |
| Terminal formatting| [Rich](https://rich.readthedocs.io/)                                |
| CLI framework      | [Click](https://click.palletsprojects.com/)                         |
| Search engine      | [Tantivy](https://github.com/quickwit-oss/tantivy) (via tantivy-py) |
| JSON parsing       | [orjson](https://github.com/ijl/orjson)                             |
| Date formatting    | [humanize](https://python-humanize.readthedocs.io/)                 |
| Type checker       | [ty](https://github.com/astral-sh/ty) (Astral)                      |

### Adding an adapter

1. Create `src/fast_resume/adapters/<agent>.py`
2. Implement the `AgentAdapter` protocol (or subclass `BaseSessionAdapter` for file-based agents)
3. Set `name`, `color`, `badge`, `supports_yolo`
4. Implement `find_sessions()`, `find_sessions_incremental()`, `get_resume_command()`, `is_available()`, `get_raw_stats()`
5. Register the adapter in `search.py` and add the agent name to the `AGENTS` dict in `config.py`
6. Bump `SCHEMA_VERSION` in `config.py`
7. Add an agent filter choice to the `--agent` option in `cli.py`
8. Write `tests/test_<agent>_adapter.py` mirroring the structure of existing adapter tests

## Configuration

`fast-resume-plus` requires no configuration file. The index lives at `~/.cache/fast-resume/`. To clear it:

```bash
rm -rf ~/.cache/fast-resume/
fr --rebuild
```

## License

MIT
