from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    workspot TEXT NOT NULL,
    server_key TEXT,
    label TEXT,
    runtime TEXT,
    container TEXT,
    repo_root TEXT,
    working_dir TEXT,
    branch TEXT,
    worktree_path TEXT,
    url TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT,
    source TEXT,
    server_session_name TEXT,
    output_file TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS servers (
    server_key TEXT PRIMARY KEY,
    workspot TEXT,
    runtime TEXT,
    container TEXT,
    pid INTEGER,
    status TEXT,
    capacity INTEGER NOT NULL DEFAULT 32,
    started_at TEXT,
    last_seen_at TEXT,
    log_file TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS session_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    workspot TEXT,
    label TEXT,
    worktree TEXT,
    started_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspots (
    name TEXT PRIMARY KEY,
    runtime TEXT NOT NULL DEFAULT 'host',
    dir TEXT NOT NULL,
    container TEXT,
    claude_bin TEXT NOT NULL DEFAULT 'claude',
    server_capacity INTEGER NOT NULL DEFAULT 32,
    env TEXT,
    metadata TEXT
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        log.info("SQLite database opened at %s", self.path)

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def migrate_from_json(
        self,
        registry_json: Path | None = None,
        history_json: Path | None = None,
        workspots_json: Path | None = None,
    ) -> None:
        """One-time migration from JSON files. Safe to call repeatedly — skips if data exists."""
        if registry_json and registry_json.exists():
            self._migrate_registry(registry_json)
        if history_json and history_json.exists():
            self._migrate_history(history_json)
        if workspots_json and workspots_json.exists():
            self._migrate_workspots(workspots_json)

    def _migrate_registry(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text())
            sessions = data.get("sessions", [])
            servers = data.get("servers", [])
            cur = self._conn.cursor()
            migrated = 0
            for s in sessions:
                cur.execute("SELECT 1 FROM sessions WHERE id = ?", (s["id"],))
                if cur.fetchone():
                    continue
                cur.execute(
                    "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        s["id"], s.get("workspot"), s.get("server_key"), s.get("label"),
                        s.get("runtime"), s.get("container"), s.get("repo_root"),
                        s.get("working_dir"), s.get("branch"), s.get("worktree_path"),
                        s.get("url"), s.get("status", "stopped"),
                        s.get("created_at"), s.get("last_seen_at"), s.get("source"),
                        s.get("server_session_name"), s.get("output_file"),
                        json.dumps(s.get("metadata") or {}),
                    ),
                )
                migrated += 1
            for sv in servers:
                cur.execute("SELECT 1 FROM servers WHERE server_key = ?", (sv["server_key"],))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO servers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (sv["server_key"], sv.get("workspot"), sv.get("runtime"),
                         sv.get("container"), sv.get("pid"), sv.get("status"),
                         sv.get("capacity", 32), sv.get("started_at"),
                         sv.get("last_seen_at"), sv.get("log_file"),
                         json.dumps(sv.get("metadata") or {})),
                    )
            self._conn.commit()
            if migrated:
                log.info("Migrated %d sessions from %s", migrated, path)
        except Exception as exc:
            log.warning("Could not migrate registry JSON: %s", exc)

    def _migrate_history(self, path: Path) -> None:
        try:
            items = json.loads(path.read_text())
            if not isinstance(items, list):
                return
            cur = self._conn.cursor()
            migrated = 0
            for item in items:
                cur.execute(
                    "INSERT INTO session_history (url, workspot, label, worktree, started_at) VALUES (?,?,?,?,?)",
                    (item.get("url"), item.get("workspot"), item.get("label"),
                     item.get("worktree"), item.get("started_at")),
                )
                migrated += 1
            self._conn.commit()
            if migrated:
                log.info("Migrated %d history entries from %s", migrated, path)
        except Exception as exc:
            log.warning("Could not migrate history JSON: %s", exc)

    def _migrate_workspots(self, path: Path) -> None:
        try:
            items = json.loads(path.read_text())
            if not isinstance(items, list):
                return
            cur = self._conn.cursor()
            migrated = 0
            for item in items:
                cur.execute("SELECT 1 FROM workspots WHERE name = ?", (item["name"],))
                if cur.fetchone():
                    continue
                cur.execute(
                    "INSERT INTO workspots VALUES (?,?,?,?,?,?,?,?)",
                    (item["name"], item.get("runtime", "host"), item["dir"],
                     item.get("container"), item.get("claude_bin", "claude"),
                     item.get("server_capacity", 32),
                     json.dumps(item.get("env") or {}),
                     json.dumps(item.get("metadata") or {})),
                )
                migrated += 1
            self._conn.commit()
            if migrated:
                log.info("Migrated %d workspots from %s", migrated, path)
        except Exception as exc:
            log.warning("Could not migrate workspots JSON: %s", exc)
