from __future__ import annotations

from datetime import datetime, timezone

from app.models import ServerRecord, ServerStatus, Workspot
from app.registry import SessionRegistry
from app.runtime import RuntimeManager


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
        )

    async def check_auth(self, workspot: Workspot) -> bool:
        runtime = self.runtime_manager.for_workspot(workspot)
        creds = (
            "/home/node/.claude/.credentials.json"
            if workspot.runtime.value == "docker"
            else "/home/claude-config/.claude/.credentials.json"
        )
        result = await runtime.run_shell(workspot, f"test -s {creds} && echo ok")
        return result.returncode == 0 and "ok" in result.stdout

    async def reconcile_server(self, workspot: Workspot) -> ServerRecord:
        runtime = self.runtime_manager.for_workspot(workspot)
        output_file = self.output_file(workspot.name)
        proc_check = await runtime.run(workspot, ["pgrep", "-f", "claude remote-control"])
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
        await runtime.run_shell(workspot, "pgrep -f 'claude remote-control' | xargs -r kill")
        await runtime.run_shell(workspot, f"rm -f {self.output_file(workspot.name)}")
        record = self.build_server_record(workspot, status=ServerStatus.stopped, log_file=self.output_file(workspot.name))
        self.registry.upsert_server(record)
        return record

    async def workspot_health(self, workspot: Workspot) -> dict:
        runtime = self.runtime_manager.for_workspot(workspot)
        git_check = await runtime.run(workspot, ["git", "-C", workspot.dir, "rev-parse", "--is-inside-work-tree"])
        auth_ok = await self.check_auth(workspot)
        server = await self.reconcile_server(workspot)
        return {
            "workspot": workspot.name,
            "runtime": workspot.runtime.value,
            "container": workspot.container,
            "dir": workspot.dir,
            "git_ok": git_check.returncode == 0,
            "auth_ok": auth_ok,
            "server_status": server.status.value,
            "server_capacity": workspot.server_capacity,
        }
