from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.models import Workspot

load_dotenv()

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppConfig:
    claude_global_flags: str
    claude_rc_flags: str
    ts_key_expires: str
    url_capture_timeout: int
    session_registry_file: Path
    session_history_file: Path
    workspot_config_file: Path
    max_sessions: int
    default_server_capacity: int
    workspots: list[Workspot]
    local_claude_env: dict[str, str]
    discovery_scan_dirs: list[str]
    discovery_docker_enabled: bool
    discovery_local_enabled: bool

    def get_workspot(self, name: str) -> Workspot | None:
        return next((workspot for workspot in self.workspots if workspot.name == name), None)


def _parse_workspots(default_server_capacity: int) -> list[Workspot]:
    raw = os.getenv("WORKSPOTS", "[]")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Failed to parse WORKSPOTS env var as JSON") from exc

    if not isinstance(parsed, list):
        raise ValueError("WORKSPOTS must be a JSON array")

    workspots: list[Workspot] = []
    names: set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("Each WORKSPOTS entry must be a JSON object")

        payload = dict(item)
        payload.setdefault("runtime", "host" if payload.get("container") in (None, "", "null") else "docker")
        payload.setdefault("claude_bin", os.getenv("DEFAULT_CLAUDE_BIN", "claude"))
        payload.setdefault("server_capacity", default_server_capacity)

        workspot = Workspot.model_validate(payload)

        if workspot.name in names:
            raise ValueError(f"Duplicate workspot name: {workspot.name}")
        if workspot.runtime.value == "docker" and not workspot.container:
            raise ValueError(f"Docker workspot '{workspot.name}' requires a container")
        if workspot.runtime.value == "host" and workspot.container:
            log.warning("Host workspot '%s' provided a container; ignoring container-specific behavior", workspot.name)

        names.add(workspot.name)
        workspots.append(workspot)

    return workspots


def load_config() -> AppConfig:
    default_server_capacity = int(os.getenv("DEFAULT_SERVER_CAPACITY", "32"))
    local_claude_env = {
        **os.environ,
        "HOME": os.getenv("LOCAL_CLAUDE_HOME", "/home/claude-config"),
        "XDG_DATA_HOME": os.getenv("LOCAL_CLAUDE_XDG_DATA_HOME", "/home/claude-share"),
    }

    scan_dirs_raw = os.getenv("DISCOVERY_SCAN_DIRS", "~/git/")
    scan_dirs = [d.strip() for d in scan_dirs_raw.split(",") if d.strip()]

    return AppConfig(
        claude_global_flags=os.getenv("CLAUDE_GLOBAL_FLAGS", ""),
        claude_rc_flags=os.getenv("CLAUDE_RC_FLAGS", ""),
        ts_key_expires=os.getenv("TS_KEY_EXPIRES", ""),
        url_capture_timeout=int(os.getenv("URL_CAPTURE_TIMEOUT", "30")),
        session_registry_file=Path(os.getenv("SESSION_REGISTRY_FILE", "/data/session-registry.json")),
        session_history_file=Path(os.getenv("SESSION_HISTORY_FILE", "/data/sessions.json")),
        workspot_config_file=Path(os.getenv("WORKSPOT_CONFIG_FILE", "/data/workspots.json")),
        max_sessions=int(os.getenv("MAX_SESSIONS", "10")),
        default_server_capacity=default_server_capacity,
        workspots=_parse_workspots(default_server_capacity),
        local_claude_env=local_claude_env,
        discovery_scan_dirs=scan_dirs,
        discovery_docker_enabled=os.getenv("DISCOVERY_DOCKER_ENABLED", "true").lower() == "true",
        discovery_local_enabled=os.getenv("DISCOVERY_LOCAL_ENABLED", "true").lower() == "true",
    )
