"""Logging configuration for fast-resume-plus."""

import logging
import os
from pathlib import Path

from .config import CACHE_DIR, LOG_FILE

# Module logger for parse errors
parse_logger = logging.getLogger("fast_resume.parse_errors")


def _restrict_permissions(path: Path, mode: int) -> None:
    """Apply restrictive permissions to a path, swallowing platform errors.

    Some filesystems (e.g. NTFS via WSL) and platforms (Windows) don't
    support POSIX chmod semantics. We don't want a permissions hint to
    crash startup, so log a warning and move on.

    Owner-only modes (0o700 / 0o600) are intentional — the cache stores
    indexed conversation content and the log can contain file paths
    that shouldn't leak to other local accounts.
    """
    try:
        os.chmod(
            path, mode
        )  # nosem: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    except OSError as e:
        logging.getLogger(__name__).warning(
            "Could not restrict permissions on %s: %s", path, e
        )


def setup_logging() -> None:
    """Set up logging with file handler for parse errors.

    Logs are written to ~/.cache/fast-resume/parse-errors.log
    """
    # Ensure cache directory exists with owner-only access. The directory
    # contains indexed conversation content from any installed agent CLI,
    # so other local accounts shouldn't be able to read it.
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _restrict_permissions(CACHE_DIR, 0o700)

    # Configure parse error logger
    parse_logger.setLevel(logging.WARNING)

    # Avoid duplicate handlers if called multiple times
    if not parse_logger.handlers:
        # File handler - append mode, rotates on size
        handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
        handler.setLevel(logging.WARNING)

        # Tighten permissions on the log file if it has been created. The
        # FileHandler only actually opens the file lazily on first write
        # in some configurations, so guard with exists().
        if LOG_FILE.exists():
            _restrict_permissions(LOG_FILE, 0o600)

        # Format: timestamp - level - message
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        parse_logger.addHandler(handler)

        # Don't propagate to root logger (avoid console output)
        parse_logger.propagate = False


def log_parse_error(
    agent: str, file_path: str | Path, error_type: str, message: str
) -> None:
    """Log a parse error to the log file.

    Args:
        agent: Which adapter encountered the error (e.g., "claude", "codex")
        file_path: Path to the problematic file
        error_type: Exception type name (e.g., "JSONDecodeError")
        message: Human-readable error message
    """
    parse_logger.warning("[%s] %s in %s: %s", agent, error_type, file_path, message)


def get_log_file_path() -> Path:
    """Return the path to the log file."""
    return LOG_FILE
