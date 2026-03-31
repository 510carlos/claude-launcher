"""Scan ~/.claude/projects/ for resumable conversations per workspace."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.models import ConversationInfo

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
MAX_READ_BYTES = 8192  # Only read first 8KB per file to find first user message


def dir_to_project_slug(directory: str) -> str:
    """Convert workspace directory to Claude project slug.

    /home/carlos/git/claude-launcher -> -home-carlos-git-claude-launcher
    """
    return "-" + directory.lstrip("/").replace("/", "-")


def list_conversations(directory: str, *, limit: int = 20) -> list[ConversationInfo]:
    """List recent Claude conversations for a workspace directory.

    Scans JSONL files in ~/.claude/projects/<slug>/, sorted by mtime descending.
    Only reads the first ~8KB of each file to extract the first user message.
    """
    slug = dir_to_project_slug(directory)
    project_dir = CLAUDE_PROJECTS_DIR / slug
    if not project_dir.is_dir():
        return []

    # Collect JSONL files with stat info
    entries: list[tuple[str, float, int]] = []  # (session_id, mtime, size)
    try:
        for entry in os.scandir(project_dir):
            if not entry.name.endswith(".jsonl") or entry.name.startswith("."):
                continue
            try:
                stat = entry.stat()
                if stat.st_size < 100:
                    continue
                session_id = entry.name[:-6]  # strip .jsonl
                entries.append((session_id, stat.st_mtime, stat.st_size))
            except OSError:
                continue
    except OSError:
        return []

    # Sort by mtime descending, take first `limit`
    entries.sort(key=lambda e: e[1], reverse=True)
    entries = entries[:limit]

    results: list[ConversationInfo] = []
    for session_id, mtime, size in entries:
        first_message = _extract_first_message(project_dir / f"{session_id}.jsonl")
        if first_message in ("(empty session)", "(unreadable)"):
            continue  # Skip forked/empty sessions
        results.append(ConversationInfo(
            session_id=session_id,
            first_message=first_message,
            last_modified=datetime.fromtimestamp(mtime, tz=timezone.utc),
            file_size=size,
        ))

    return results


def _extract_first_message(path: Path) -> str:
    """Read first ~8KB of a JSONL file and extract the first user message."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            chunk = f.read(MAX_READ_BYTES)
    except OSError:
        return "(unreadable)"

    for line in chunk.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if record.get("type") != "user":
            continue
        message = record.get("message", {})
        if message.get("role") != "user":
            continue

        content = message.get("content", "")
        if isinstance(content, str):
            return content[:120].strip() or "(empty)"
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")[:120].strip() or "(empty)"

    return "(empty session)"
