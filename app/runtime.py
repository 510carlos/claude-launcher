from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional, Protocol

from models import RuntimeType, Workspot


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class RuntimeAdapter(Protocol):
    async def run(self, workspot: Workspot, args: list[str], *, cwd: Optional[str] = None) -> CommandResult: ...
    async def run_shell(self, workspot: Workspot, command: str, *, cwd: Optional[str] = None, detached: bool = False) -> CommandResult: ...


class DockerRuntimeAdapter:
    def __init__(self, local_env: Optional[dict[str, str]] = None):
        self.local_env = local_env or {}

    async def run(self, workspot: Workspot, args: list[str], *, cwd: Optional[str] = None) -> CommandResult:
        docker_args = ["docker", "exec"]
        if cwd:
            docker_args.extend(["-w", cwd])
        docker_args.extend([workspot.container, *args])
        proc = await asyncio.create_subprocess_exec(
            *docker_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return CommandResult(proc.returncode, stdout.decode(), stderr.decode())

    async def run_shell(self, workspot: Workspot, command: str, *, cwd: Optional[str] = None, detached: bool = False) -> CommandResult:
        docker_args = ["docker", "exec"]
        if detached:
            docker_args.append("-d")
        if cwd:
            docker_args.extend(["-w", cwd])
        docker_args.extend([workspot.container, "bash", "-lc", command])
        proc = await asyncio.create_subprocess_exec(
            *docker_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return CommandResult(proc.returncode, stdout.decode(), stderr.decode())


class HostRuntimeAdapter:
    def __init__(self, local_env: Optional[dict[str, str]] = None):
        self.local_env = local_env or {}

    async def run(self, workspot: Workspot, args: list[str], *, cwd: Optional[str] = None) -> CommandResult:
        env = {**self.local_env, **workspot.env}
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        return CommandResult(proc.returncode, stdout.decode(), stderr.decode())

    async def run_shell(self, workspot: Workspot, command: str, *, cwd: Optional[str] = None, detached: bool = False) -> CommandResult:
        env = {**self.local_env, **workspot.env}
        proc = await asyncio.create_subprocess_exec(
            "bash", "-lc", command,
            stdout=asyncio.subprocess.DEVNULL if detached else asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
            start_new_session=detached,
        )
        stdout, stderr = await proc.communicate()
        return CommandResult(proc.returncode, (stdout or b"").decode(), stderr.decode())


class RuntimeManager:
    def __init__(self, local_env: Optional[dict[str, str]] = None):
        self.docker = DockerRuntimeAdapter(local_env=local_env)
        self.host = HostRuntimeAdapter(local_env=local_env)

    def for_workspot(self, workspot: Workspot) -> RuntimeAdapter:
        if workspot.runtime == RuntimeType.docker:
            return self.docker
        return self.host
