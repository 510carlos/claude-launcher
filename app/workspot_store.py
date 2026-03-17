from __future__ import annotations

import json
import logging
from pathlib import Path

from app.models import Workspot, WorkspotSource

log = logging.getLogger(__name__)


class WorkspotStore:
    """Persistent file-backed workspot configuration."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[Workspot]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
            items = data if isinstance(data, list) else data.get("workspots", [])
            return [Workspot.model_validate({**item, "source": "file"}) for item in items]
        except Exception:
            log.warning("Failed to load workspot store from %s", self.path)
            return []

    def save(self, workspots: list[Workspot]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [ws.model_dump(mode="json", exclude={"source"}) for ws in workspots]
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.rename(self.path)

    def add(self, workspot: Workspot) -> Workspot:
        workspots = self.load()
        if any(ws.name == workspot.name for ws in workspots):
            raise ValueError(f"Workspot '{workspot.name}' already exists")
        ws = workspot.model_copy(update={"source": WorkspotSource.file})
        workspots.append(ws)
        self.save(workspots)
        return ws

    def remove(self, name: str) -> bool:
        workspots = self.load()
        filtered = [ws for ws in workspots if ws.name != name]
        if len(filtered) == len(workspots):
            return False
        self.save(filtered)
        return True

    def merge_with_env(self, env_workspots: list[Workspot]) -> list[Workspot]:
        """Merge env-defined workspots with file-defined ones. Env wins on name collision."""
        env_names = {ws.name for ws in env_workspots}
        file_workspots = [ws for ws in self.load() if ws.name not in env_names]
        return env_workspots + file_workspots
