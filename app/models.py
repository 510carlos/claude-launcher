from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class RuntimeType(str, Enum):
    docker = "docker"
    host = "host"


class WorkspotSource(str, Enum):
    env = "env"
    file = "file"


class DiscoveryCompatibility(str, Enum):
    compatible = "compatible"
    partial = "partial"
    incompatible = "incompatible"


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
    source: WorkspotSource = WorkspotSource.env

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
    output_file: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegistryState(BaseModel):
    servers: list[ServerRecord] = Field(default_factory=list)
    sessions: list[SessionRecord] = Field(default_factory=list)


class StartRequest(BaseModel):
    workspot: str
    worktree: bool = False
    label: Optional[str] = None
    branch: Optional[str] = None
    directory: Optional[str] = None


class KillRequest(BaseModel):
    workspot: str


class SessionHookPayload(BaseModel):
    session_id: Optional[str] = None
    workspot: Optional[str] = None
    label: Optional[str] = None
    url: Optional[str] = None
    branch: Optional[str] = None
    status: SessionStatus = SessionStatus.running
    source: str = "hook"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveredEnvironment(BaseModel):
    name: str
    runtime: RuntimeType
    dir: str
    container: Optional[str] = None
    claude_bin: Optional[str] = None
    compatibility: DiscoveryCompatibility
    checks: dict[str, bool] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    already_configured: bool = False
    image: Optional[str] = None
    container_status: Optional[str] = None


class AddWorkspotRequest(BaseModel):
    name: str
    runtime: RuntimeType = RuntimeType.host
    dir: str
    container: Optional[str] = None
    claude_bin: str = "claude"
    server_capacity: int = 32
    env: dict[str, str] = Field(default_factory=dict)
