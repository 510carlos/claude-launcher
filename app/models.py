from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class RuntimeType(str, Enum):
    docker = "docker"
    host = "host"


class ServerStatus(str, Enum):
    unknown = "unknown"
    running = "running"
    stopped = "stopped"
    unhealthy = "unhealthy"


class SessionStatus(str, Enum):
    pending = "pending"
    running = "running"
    stopped = "stopped"
    failed = "failed"


class Workspot(BaseModel):
    name: str
    runtime: RuntimeType = RuntimeType.docker
    dir: str
    container: Optional[str] = None
    claude_bin: str = "claude"
    server_capacity: int = 32
    env: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("container")
    @classmethod
    def normalize_container(cls, value: Optional[str]) -> Optional[str]:
        if value in ("", "null"):
            return None
        return value

    @field_validator("server_capacity")
    @classmethod
    def validate_capacity(cls, value: int) -> int:
        if value < 1:
            raise ValueError("server_capacity must be >= 1")
        return value


class ServerRecord(BaseModel):
    workspot: str
    server_key: str
    runtime: RuntimeType
    container: Optional[str] = None
    status: ServerStatus = ServerStatus.unknown
    capacity: int = 32
    started_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    log_file: Optional[str] = None
    pid: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionRecord(BaseModel):
    id: str
    workspot: str
    server_key: str
    label: str
    runtime: RuntimeType
    container: Optional[str] = None
    repo_root: str
    working_dir: str
    branch: Optional[str] = None
    worktree_path: Optional[str] = None
    url: Optional[str] = None
    status: SessionStatus = SessionStatus.pending
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    source: str = "launcher"
    server_session_name: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegistryState(BaseModel):
    servers: list[ServerRecord] = Field(default_factory=list)
    sessions: list[SessionRecord] = Field(default_factory=list)


class StartRequest(BaseModel):
    workspot: str
    worktree: bool = False


class KillRequest(BaseModel):
    workspot: str
