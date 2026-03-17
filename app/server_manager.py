from __future__ import annotations

import time
from datetime import datetime, timezone

from app.models import ServerRecord, ServerStatus, Workspot
from app.registry import SessionRegistry
from app.runtime import RuntimeManager

# Trust check cache: workspot_name -> (trusted, message, timestamp)
_trust_cache: dict[str, tuple[bool, str, float]] = {}
TRUST_CACHE_TTL = 300  # 5 minutes


class ServerManager:
    def __init__(self, registry: SessionRegistry, runtime_manager: RuntimeManager):
        self.registry = registry
        self.runtime_manager = runtime_manager

    def server_key(self, workspot: Workspot) -> str:
        return workspot.name

    def output_file(self, workspot_name: str) -> str:
        return f"/tmp/claude-rc-{workspot_name}.txt"

    def build_server_record(
        self,
        workspot: Workspot,
        *,
        status: ServerStatus,
        log_file: str | None = None,
        started_at: datetime | None = None,
    ) -> ServerRecord:
        now = datetime.now(timezone.utc)
        return ServerRecord(
            workspot=workspot.name,
            server_key=self.server_key(workspot),
            runtime=workspot.runtime,
            container=workspot.container,
            status=status,
            capacity=workspot.server_capacity,
            last_seen_at=now,
            started_at=started_at if status == ServerStatus.running else None,
            log_file=log_file,
            metadata={"claude_bin": workspot.claude_bin},
        )

    async def check_auth(self, workspot: Workspot) -> bool:
        runtime = self.runtime_manager.for_workspot(workspot)
        home = workspot.env.get("HOME", "~")
        creds = workspot.env.get("CLAUDE_CREDENTIALS_PATH") or f"{home}/.claude/.credentials.json"
        result = await runtime.run_shell(workspot, f"test -s {creds} && echo ok")
        return result.returncode == 0 and "ok" in result.stdout

    async def check_workspace_trust(self, workspot: Workspot) -> tuple[bool, str]:
        """Check if the workspace directory is trusted by Claude.

        Results cached for 5 minutes since trust status rarely changes.
        """
        # Check cache first
        cached = _trust_cache.get(workspot.name)
        if cached and (time.monotonic() - cached[2]) < TRUST_CACHE_TTL:
            return cached[0], cached[1]

        runtime = self.runtime_manager.for_workspot(workspot)
        result = await runtime.run_shell(
            workspot,
            f"timeout 3 {workspot.claude_bin} remote-control --name __trust_check 2>&1 || true",
            cwd=workspot.dir,
        )
        output = (result.stdout + result.stderr).strip().lower()
        if "not trusted" in output or "workspace trust" in output:
            res = (False, f"Workspace not trusted — run `claude` in {workspot.dir} to accept")
        else:
            res = (True, "")

        _trust_cache[workspot.name] = (res[0], res[1], time.monotonic())
        return res

    async def check_preflight(self, workspot: Workspot) -> list[str]:
        """Run all pre-flight checks, return list of issues (empty = all good)."""
        issues: list[str] = []
        runtime = self.runtime_manager.for_workspot(workspot)

        # 1. Runtime accessible
        adapter_health = await runtime.health(workspot)
        if not adapter_health["runtime_ok"]:
            err = adapter_health.get("runtime_error", "")
            issues.append(f"Runtime not accessible: {err}" if err else "Runtime not accessible")
            return issues  # can't check anything else

        # 2. Repo exists
        if not adapter_health["repo_exists"]:
            issues.append(f"Directory not found: {workspot.dir}")

        # 3. Git
        if not adapter_health["git_ok"]:
            issues.append("Git not available or not a git repo")

        # 4. Claude CLI
        if not adapter_health["claude_bin_ok"]:
            issues.append(f"Claude CLI not found at {workspot.claude_bin}")
            return issues  # can't check auth/trust without CLI

        # 5. Auth
        if not await self.check_auth(workspot):
            issues.append("Not authenticated — run `claude login`")

        # 6. Workspace trust
        trusted, trust_msg = await self.check_workspace_trust(workspot)
        if not trusted:
            issues.append(trust_msg)

        return issues

    async def reconcile_server(self, workspot: Workspot) -> ServerRecord:
        runtime = self.runtime_manager.for_workspot(workspot)
        output_file = self.output_file(workspot.name)
        # Use workspot name in pattern to avoid false positives in shared containers
        proc_check = await runtime.run_shell(workspot, f"pgrep -af 'CLAUDE_LAUNCHER_WORKSPOT=\"{workspot.name}\"'")
        if proc_check.returncode != 0:
            record = self.build_server_record(workspot, status=ServerStatus.stopped, log_file=output_file)
            self.registry.upsert_server(record)
            return record

        existing = next(
            (item for item in self.registry.list_servers() if item.server_key == self.server_key(workspot)),
            None,
        )
        record = self.build_server_record(
            workspot,
            status=ServerStatus.running,
            log_file=output_file,
            started_at=(existing.started_at if existing and existing.started_at else datetime.now(timezone.utc)),
        )
        self.registry.upsert_server(record)
        return record

    async def ensure_server(self, workspot: Workspot) -> ServerRecord:
        return await self.reconcile_server(workspot)

    async def stop_server(self, workspot: Workspot) -> ServerRecord:
        runtime = self.runtime_manager.for_workspot(workspot)
        await runtime.run_shell(workspot, f"pgrep -f 'CLAUDE_LAUNCHER_WORKSPOT=\"{workspot.name}\"' | xargs -r kill")
        await runtime.run_shell(workspot, f"rm -f {self.output_file(workspot.name)}")
        record = self.build_server_record(workspot, status=ServerStatus.stopped, log_file=self.output_file(workspot.name))
        self.registry.upsert_server(record)
        return record

    async def workspot_health(self, workspot: Workspot) -> dict:
        runtime = self.runtime_manager.for_workspot(workspot)
        adapter_health = await runtime.health(workspot)
        issues: list[str] = []

        # Early bail if runtime is down — can't check anything else
        if not adapter_health["runtime_ok"]:
            issues.append("Container not running" if workspot.container else "Host unreachable")
            return {
                "workspot": workspot.name, "runtime": workspot.runtime.value,
                "container": workspot.container, "dir": workspot.dir, "claude_bin": workspot.claude_bin,
                "runtime_ok": False, "repo_exists": False, "claude_bin_ok": False,
                "git_ok": False, "runtime_error": adapter_health.get("runtime_error", ""),
                "auth_ok": False, "trusted": False,
                "server_status": "stopped", "server_capacity": workspot.server_capacity,
                "issues": issues,
            }

        if not adapter_health["repo_exists"]:
            issues.append(f"Directory not found: {workspot.dir}")
        if not adapter_health["git_ok"]:
            issues.append("Git not available")

        # Only check auth/trust if CLI exists
        auth_ok = False
        trusted = False
        if not adapter_health["claude_bin_ok"]:
            issues.append(f"Claude CLI not found at {workspot.claude_bin}")
        else:
            auth_ok = await self.check_auth(workspot)
            if not auth_ok:
                issues.append("Not authenticated — run claude login")
            trusted, trust_msg = await self.check_workspace_trust(workspot)
            if not trusted:
                issues.append(trust_msg)

        server = await self.reconcile_server(workspot)

        return {
            "workspot": workspot.name, "runtime": workspot.runtime.value,
            "container": workspot.container, "dir": workspot.dir, "claude_bin": workspot.claude_bin,
            "runtime_ok": adapter_health["runtime_ok"],
            "repo_exists": adapter_health["repo_exists"],
            "claude_bin_ok": adapter_health["claude_bin_ok"],
            "git_ok": adapter_health["git_ok"],
            "runtime_error": adapter_health.get("runtime_error", ""),
            "auth_ok": auth_ok, "trusted": trusted,
            "server_status": server.status.value,
            "server_capacity": workspot.server_capacity,
            "issues": issues,
        }
