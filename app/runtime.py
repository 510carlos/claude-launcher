from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Optional, Protocol

from app.models import RuntimeType, Workspot


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class RuntimeAdapter(Protocol):
    async def run(self, workspot: Workspot, args: list[str], *, cwd: Optional[str] = None) -> CommandResult: ...
    async def run_shell(self, workspot: Workspot, command: str, *, cwd: Optional[str] = None, detached: bool = False) -> CommandResult: ...
    async def health(self, workspot: Workspot) -> dict: ...


class DockerRuntimeAdapter:
    def __init__(self, local_env: Optional[dict[str, str]] = None):
        self.local_env = local_env or {}

    def _env_args(self, workspot: Workspot) -> list[str]:
        # Only pass workspot-level env + essential overrides (HOME, XDG).
        # Do NOT pass full host os.environ — that leaks secrets into containers.
        essential = {}
        for key in ("HOME", "XDG_DATA_HOME"):
            if key in self.local_env:
                essential[key] = self.local_env[key]
        args: list[str] = []
        for key, value in {**essential, **workspot.env}.items():
            args.extend(["-e", f"{key}={value}"])
        return args

    async def run(self, workspot: Workspot, args: list[str], *, cwd: Optional[str] = None) -> CommandResult:
        docker_args = ["docker", "exec", *self._env_args(workspot)]
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
        docker_args.extend(self._env_args(workspot))
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

    async def health(self, workspot: Workspot) -> dict:
        inspect = await asyncio.create_subprocess_exec(
            "docker", "inspect", "-f", "{{.State.Running}}", workspot.container or "",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await inspect.communicate()
        runtime_ok = inspect.returncode == 0 and stdout.decode().strip() == "true"
        repo_exists = False
        claude_bin_ok = False
        git_ok = False
        if runtime_ok:
            repo_exists = (await self.run_shell(workspot, f"test -d {workspot.dir} && echo ok")).returncode == 0
            claude_bin_ok = (await self.run_shell(workspot, f"command -v {workspot.claude_bin}")).returncode == 0
            git_ok = (await self.run_shell(workspot, f"git -C {workspot.dir} rev-parse --is-inside-work-tree")).returncode == 0
        return {
            "runtime_ok": runtime_ok,
            "repo_exists": repo_exists,
            "claude_bin_ok": claude_bin_ok,
            "git_ok": git_ok,
            "runtime_error": stderr.decode().strip(),
        }


class HostRuntimeAdapter:
    def __init__(self, local_env: Optional[dict[str, str]] = None):
        self.local_env = local_env or {}

    def _env(self, workspot: Workspot) -> dict[str, str]:
        # Host workspots use the real OS environment; only overlay workspot-level env.
        # Deliberately skip self.local_env (HOME/XDG overrides meant for Docker).
        return {**os.environ, **workspot.env}

    async def run(self, workspot: Workspot, args: list[str], *, cwd: Optional[str] = None) -> CommandResult:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env(workspot),
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        return CommandResult(proc.returncode, stdout.decode(), stderr.decode())

    async def run_shell(self, workspot: Workspot, command: str, *, cwd: Optional[str] = None, detached: bool = False) -> CommandResult:
        proc = await asyncio.create_subprocess_exec(
            "bash", "-lc", command,
            stdout=asyncio.subprocess.DEVNULL if detached else asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env(workspot),
            cwd=cwd,
            start_new_session=detached,
        )
        stdout, stderr = await proc.communicate()
        return CommandResult(proc.returncode, (stdout or b"").decode(), stderr.decode())

    async def health(self, workspot: Workspot) -> dict:
        repo_exists = os.path.isdir(workspot.dir)
        claude_bin_ok = (await self.run_shell(workspot, f"command -v {workspot.claude_bin}")).returncode == 0
        git_ok = repo_exists and (await self.run_shell(workspot, f"git -C {workspot.dir} rev-parse --is-inside-work-tree")).returncode == 0
        return {
            "runtime_ok": True,
            "repo_exists": repo_exists,
            "claude_bin_ok": claude_bin_ok,
            "git_ok": git_ok,
            "runtime_error": "",
        }


class RuntimeManager:
    def __init__(self, local_env: Optional[dict[str, str]] = None):
        self.docker = DockerRuntimeAdapter(local_env=local_env)
        self.host = HostRuntimeAdapter(local_env=local_env)

    def for_workspot(self, workspot: Workspot) -> RuntimeAdapter:
        if workspot.runtime == RuntimeType.docker:
            return self.docker
        return self.host
