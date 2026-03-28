from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.db import Database
from app.models import ServerRecord, SessionRecord, SessionStatus

log = logging.getLogger(__name__)


def _row_to_session(row) -> SessionRecord:
    d = dict(row)
    if isinstance(d.get("metadata"), str):
        d["metadata"] = json.loads(d["metadata"] or "{}")
    return SessionRecord.model_validate(d)


def _row_to_server(row) -> ServerRecord:
    d = dict(row)
    if isinstance(d.get("metadata"), str):
        d["metadata"] = json.loads(d["metadata"] or "{}")
    return ServerRecord.model_validate(d)


class SessionRegistry:
    def __init__(self, db: Database):
        self.db = db

    def upsert_server(self, record: ServerRecord) -> ServerRecord:
        d = record.model_dump(mode="json")
        self.db.conn.execute(
            """INSERT INTO servers
               (server_key, workspot, runtime, container, pid, status, capacity,
                started_at, last_seen_at, log_file, metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(server_key) DO UPDATE SET
               workspot=excluded.workspot, runtime=excluded.runtime,
               container=excluded.container, pid=excluded.pid,
               status=excluded.status, capacity=excluded.capacity,
               started_at=excluded.started_at, last_seen_at=excluded.last_seen_at,
               log_file=excluded.log_file, metadata=excluded.metadata""",
            (d["server_key"], d.get("workspot"), d.get("runtime"), d.get("container"),
             d.get("pid"), d.get("status"), d.get("capacity", 32),
             d.get("started_at"), d.get("last_seen_at"), d.get("log_file"),
             json.dumps(d.get("metadata") or {})),
        )
        self.db.conn.commit()
        return record

    def upsert_session(self, record: SessionRecord) -> SessionRecord:
        d = record.model_dump(mode="json")
        self.db.conn.execute(
            """INSERT INTO sessions
               (id, workspot, server_key, label, runtime, container, repo_root,
                working_dir, branch, worktree_path, url, status, created_at,
                last_seen_at, source, server_session_name, output_file, metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
               workspot=excluded.workspot, server_key=excluded.server_key,
               label=excluded.label, runtime=excluded.runtime,
               container=excluded.container, repo_root=excluded.repo_root,
               working_dir=excluded.working_dir, branch=excluded.branch,
               worktree_path=excluded.worktree_path, url=excluded.url,
               status=excluded.status, last_seen_at=excluded.last_seen_at,
               source=excluded.source,
               server_session_name=excluded.server_session_name,
               output_file=excluded.output_file, metadata=excluded.metadata""",
            (
                d["id"], d.get("workspot"), d.get("server_key"), d.get("label"),
                d.get("runtime"), d.get("container"), d.get("repo_root"),
                d.get("working_dir"), d.get("branch"), d.get("worktree_path"),
                d.get("url"), d.get("status", "stopped"),
                d.get("created_at"), d.get("last_seen_at"), d.get("source"),
                d.get("server_session_name"), d.get("output_file"),
                json.dumps(d.get("metadata") or {}),
            ),
        )
        self.db.conn.commit()
        return record

    def delete_session(self, session_id: str) -> bool:
        cur = self.db.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.db.conn.commit()
        return cur.rowcount > 0

    def delete_ended_sessions(self) -> int:
        cur = self.db.conn.execute(
            "DELETE FROM sessions WHERE status IN ('stopped', 'failed')"
        )
        self.db.conn.commit()
        return cur.rowcount

    def get_session(self, session_id: str) -> SessionRecord | None:
        row = self.db.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return _row_to_session(row) if row else None

    def find_session(
        self,
        *,
        session_id: str | None = None,
        workspot: str | None = None,
        label: str | None = None,
        statuses: set[SessionStatus] | None = None,
    ) -> SessionRecord | None:
        if session_id:
            return self.get_session(session_id)

        conditions: list[str] = []
        params: list = []
        if workspot:
            conditions.append("workspot = ?")
            params.append(workspot)
        if label:
            conditions.append("label = ?")
            params.append(label)
        if statuses:
            placeholders = ",".join("?" * len(statuses))
            conditions.append(f"status IN ({placeholders})")
            params.extend(s.value for s in statuses)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.db.conn.execute(
            f"SELECT * FROM sessions {where} ORDER BY created_at DESC LIMIT 1",
            params,
        ).fetchall()
        return _row_to_session(rows[0]) if rows else None

    def mark_session(
        self,
        session_id: str,
        *,
        status: SessionStatus | None = None,
        url: str | None = None,
        branch: str | None = None,
        metadata: dict | None = None,
        source: str | None = None,
    ) -> SessionRecord | None:
        session = self.get_session(session_id)
        if not session:
            return None

        now = datetime.now(timezone.utc).isoformat()
        new_meta = json.dumps({**session.metadata, **(metadata or {})})

        self.db.conn.execute(
            """UPDATE sessions SET
               status = COALESCE(?, status),
               url = CASE WHEN ? IS NOT NULL THEN ? ELSE url END,
               branch = CASE WHEN ? IS NOT NULL THEN ? ELSE branch END,
               last_seen_at = ?,
               source = COALESCE(?, source),
               metadata = ?
               WHERE id = ?""",
            (
                status.value if status else None,
                url, url,
                branch, branch,
                now,
                source,
                new_meta,
                session_id,
            ),
        )
        self.db.conn.commit()
        return self.get_session(session_id)

    def list_sessions(self, *, workspot: Optional[str] = None) -> list[SessionRecord]:
        if workspot:
            rows = self.db.conn.execute(
                "SELECT * FROM sessions WHERE workspot = ? ORDER BY created_at DESC",
                (workspot,),
            ).fetchall()
        else:
            rows = self.db.conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_session(r) for r in rows]

    def list_servers(self) -> list[ServerRecord]:
        rows = self.db.conn.execute(
            "SELECT * FROM servers ORDER BY server_key"
        ).fetchall()
        return [_row_to_server(r) for r in rows]


class SessionHistoryStore:
    def __init__(self, db: Database, max_sessions: int = 10):
        self.db = db
        self.max_sessions = max_sessions

    def load(self) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT url, workspot, label, worktree, started_at "
            "FROM session_history ORDER BY started_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def save_session(
        self,
        url: str,
        workspot: str,
        worktree: str | None = None,
        label: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.db.conn.execute(
            "INSERT INTO session_history (url, workspot, label, worktree, started_at) "
            "VALUES (?,?,?,?,?)",
            (url, workspot, label, worktree, now),
        )
        self.db.conn.execute(
            """DELETE FROM session_history WHERE id NOT IN (
               SELECT id FROM session_history ORDER BY started_at DESC LIMIT ?
            )""",
            (self.max_sessions,),
        )
        self.db.conn.commit()
