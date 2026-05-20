"""Configuration and constants for fast-resume-plus."""

import os
from pathlib import Path

# Agent colors and badges (badge is the display name shown in UI)
AGENTS = {
    "claude": {"color": "#E87B35", "badge": "claude"},
    "codex": {"color": "#00A67E", "badge": "codex"},
    "opencode": {"color": "#CFCECD", "badge": "opencode"},
    "vibe": {"color": "#FF6B35", "badge": "vibe"},
    "crush": {"color": "#6B51FF", "badge": "crush"},
    "copilot-cli": {"color": "#9CA3AF", "badge": "copilot"},
    "copilot-vscode": {"color": "#007ACC", "badge": "vscode"},
    "gemini": {"color": "#4285F4", "badge": "gemini"},
    "kiro": {"color": "#5C1FFB", "badge": "kiro"},
    "antigravity": {"color": "#9333EA", "badge": "antigravity"},
}

# Storage paths
CLAUDE_DIR = Path.home() / ".claude" / "projects"
CODEX_DIR = Path.home() / ".codex" / "sessions"
OPENCODE_DIR = Path.home() / ".local" / "share" / "opencode"
OPENCODE_LEGACY_DIR = OPENCODE_DIR / "storage"
OPENCODE_DB = OPENCODE_DIR / "opencode.db"
VIBE_DIR = Path.home() / ".vibe" / "logs" / "session"
CRUSH_PROJECTS_FILE = Path.home() / ".local" / "share" / "crush" / "projects.json"
COPILOT_DIR = Path.home() / ".copilot" / "session-state"
GEMINI_DIR = Path.home() / ".gemini"
KIRO_DIR = Path.home() / ".kiro" / "sessions" / "cli"
ANTIGRAVITY_DIR = Path.home() / ".gemini" / "antigravity-cli"
ANTIGRAVITY_CONVERSATIONS_DIR = ANTIGRAVITY_DIR / "conversations"
ANTIGRAVITY_HISTORY_FILE = ANTIGRAVITY_DIR / "history.jsonl"

# Storage location
CACHE_DIR = Path.home() / ".cache" / "fast-resume"
INDEX_DIR = CACHE_DIR / "tantivy_index"
LOG_FILE = CACHE_DIR / "parse-errors.log"
SCHEMA_VERSION = 23  # Bump when schema changes (23: rename agy → antigravity)

# Per-agent binary overrides read from environment variables.
# Set FAST_RESUME_<AGENT>_BIN to an absolute path to use a binary that isn't on PATH.
# Hyphens in agent names become underscores: FAST_RESUME_COPILOT_CLI_BIN, etc.
BIN_OVERRIDES: dict[str, str] = {
    agent: path
    for agent in AGENTS
    if (path := os.environ.get(f"FAST_RESUME_{agent.upper().replace('-', '_')}_BIN"))
}
