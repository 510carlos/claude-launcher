from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models import RegistryState, ServerRecord, SessionRecord


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

    def save_session(self, url: str, workspot: str, worktree: str | None = None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        sessions = self.load()
        sessions.insert(0, {
            "url": url,
            "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "workspot": workspot,
            "worktree": worktree,
        })
        sessions = sessions[: self.max_sessions]
        self.path.write_text(json.dumps(sessions, indent=2))
