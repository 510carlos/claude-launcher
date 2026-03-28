from __future__ import annotations

import json
import logging

from app.db import Database
from app.models import Workspot, WorkspotSource

log = logging.getLogger(__name__)


class WorkspotStore:
    """SQLite-backed workspot configuration."""

    def __init__(self, db: Database):
        self.db = db

    def load(self) -> list[Workspot]:
        rows = self.db.conn.execute("SELECT * FROM workspots").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("env"), str):
                d["env"] = json.loads(d["env"] or "{}")
            if isinstance(d.get("metadata"), str):
                d["metadata"] = json.loads(d["metadata"] or "{}")
            result.append(Workspot.model_validate({**d, "source": "file"}))
        return result

    def add(self, workspot: Workspot) -> Workspot:
        existing = self.db.conn.execute(
            "SELECT 1 FROM workspots WHERE name = ?", (workspot.name,)
        ).fetchone()
        if existing:
            raise ValueError(f"Workspot '{workspot.name}' already exists")
        d = workspot.model_dump(mode="json")
        self.db.conn.execute(
            "INSERT INTO workspots "
            "(name, runtime, dir, container, claude_bin, server_capacity, env, metadata) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (workspot.name, d["runtime"], workspot.dir, workspot.container,
             workspot.claude_bin, workspot.server_capacity,
             json.dumps(d.get("env") or {}), json.dumps(d.get("metadata") or {})),
        )
        self.db.conn.commit()
        return workspot.model_copy(update={"source": WorkspotSource.file})

    def remove(self, name: str) -> bool:
        cur = self.db.conn.execute("DELETE FROM workspots WHERE name = ?", (name,))
        self.db.conn.commit()
        return cur.rowcount > 0

    def merge_with_env(self, env_workspots: list[Workspot]) -> list[Workspot]:
        """Merge env-defined workspots with file-defined ones. Env wins on name collision."""
        env_names = {ws.name for ws in env_workspots}
        file_workspots = [ws for ws in self.load() if ws.name not in env_names]
        return env_workspots + file_workspots
