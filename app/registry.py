from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models import RegistryState, ServerRecord, SessionRecord, SessionStatus


class SessionRegistry:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> RegistryState:
        if not self.path.exists():
            return RegistryState()

        try:
            return RegistryState.model_validate_json(self.path.read_text())
        except Exception:
            return RegistryState()

    def save(self, state: RegistryState) -> RegistryState:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state.model_dump(mode="json"), indent=2))
        return state

    def upsert_server(self, record: ServerRecord) -> ServerRecord:
        state = self.load()
        for index, existing in enumerate(state.servers):
            if existing.server_key == record.server_key:
                state.servers[index] = record
                self.save(state)
                return record
        state.servers.append(record)
        self.save(state)
        return record

    def upsert_session(self, record: SessionRecord) -> SessionRecord:
        state = self.load()
        for index, existing in enumerate(state.sessions):
            if existing.id == record.id:
                state.sessions[index] = record
                self.save(state)
                return record
        state.sessions.append(record)
        self.save(state)
        return record

    def delete_session(self, session_id: str) -> bool:
        state = self.load()
        original_count = len(state.sessions)
        state.sessions = [session for session in state.sessions if session.id != session_id]
        if len(state.sessions) == original_count:
            return False
        self.save(state)
        return True

    def get_session(self, session_id: str) -> SessionRecord | None:
        return next((item for item in self.load().sessions if item.id == session_id), None)

    def find_session(
        self,
        *,
        session_id: str | None = None,
        workspot: str | None = None,
        label: str | None = None,
        statuses: set[SessionStatus] | None = None,
    ) -> SessionRecord | None:
        candidates = self.load().sessions
        if session_id:
            return next((item for item in candidates if item.id == session_id), None)
        if workspot:
            candidates = [item for item in candidates if item.workspot == workspot]
        if label:
            candidates = [item for item in candidates if item.label == label]
        if statuses:
            candidates = [item for item in candidates if item.status in statuses]
        candidates = sorted(candidates, key=lambda item: item.created_at, reverse=True)
        return candidates[0] if candidates else None

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
        state = self.load()
        now = datetime.now(timezone.utc)
        for index, session in enumerate(state.sessions):
            if session.id != session_id:
                continue
            updated = session.model_copy(
                update={
                    "status": status or session.status,
                    "url": url if url is not None else session.url,
                    "branch": branch if branch is not None else session.branch,
                    "last_seen_at": now,
                    "source": source or session.source,
                    "metadata": {**session.metadata, **(metadata or {})},
                }
            )
            state.sessions[index] = updated
            self.save(state)
            return updated
        return None

    def list_sessions(self, *, workspot: Optional[str] = None) -> list[SessionRecord]:
        state = self.load()
        sessions = state.sessions
        if workspot:
            sessions = [session for session in sessions if session.workspot == workspot]
        return sorted(sessions, key=lambda item: item.created_at, reverse=True)

    def list_servers(self) -> list[ServerRecord]:
        return sorted(self.load().servers, key=lambda item: item.server_key)


class SessionHistoryStore:
    def __init__(self, path: Path, max_sessions: int = 10):
        self.path = path
        self.max_sessions = max_sessions

    def load(self) -> list[dict]:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                if isinstance(data, list):
                    return data
            except Exception:
                return []
        return []

    def save_session(self, url: str, workspot: str, worktree: str | None = None, label: str | None = None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        sessions = self.load()
        sessions.insert(0, {
            "url": url,
            "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "workspot": workspot,
            "worktree": worktree,
            "label": label,
        })
        sessions = sessions[: self.max_sessions]
        self.path.write_text(json.dumps(sessions, indent=2))
