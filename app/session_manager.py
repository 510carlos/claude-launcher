from __future__ import annotations

import asyncio
import re
import secrets
import time
from datetime import datetime, timezone

from app.models import SessionRecord, SessionStatus, StartRequest, Workspot
from app.registry import SessionHistoryStore, SessionRegistry
from app.runtime import RuntimeManager
from app.server_manager import ServerManager


class SessionManager:
    def __init__(
        self,
        *,
        config,
        registry: SessionRegistry,
        history_store: SessionHistoryStore,
        runtime_manager: RuntimeManager,
        server_manager: ServerManager,
    ):
        self.config = config
        self.registry = registry
        self.history_store = history_store
        self.runtime_manager = runtime_manager
        self.server_manager = server_manager

    def _runtime(self, workspot: Workspot):
        return self.runtime_manager.for_workspot(workspot)

    async def poll_for_url(self, workspot: Workspot, output_file: str) -> tuple[str | None, str]:
        runtime = self._runtime(workspot)
        deadline = time.monotonic() + self.config.url_capture_timeout
        last_output = ""
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            result = await runtime.run(workspot, ["cat", output_file])
            if result.returncode == 0:
                last_output = result.stdout.strip()
                match = re.search(r"https://claude\.ai/code\S+", result.stdout)
                if match:
                    return match.group(0), last_output
        return None, last_output

    async def existing_session_url(self, workspot: Workspot) -> str | None:
        runtime = self._runtime(workspot)
        output_file = self.server_manager.output_file(workspot.name)
        record = await self.server_manager.reconcile_server(workspot)
        if record.status != SessionStatus.running:
            return None
        output = await runtime.run(workspot, ["cat", output_file])
        if output.returncode == 0:
            match = re.search(r"https://claude\.ai/code\S+", output.stdout)
            if match:
                return match.group(0)
        await self.server_manager.stop_server(workspot)
        return None

    async def launch_session(self, workspot: Workspot, working_dir: str, output_file: str) -> tuple[bool, str]:
        runtime = self._runtime(workspot)
        flags = " ".join(
            part
            for part in [self.config.claude_global_flags, workspot.claude_bin, "remote-control", self.config.claude_rc_flags]
            if part
        ).strip()
        if workspot.runtime.value == "docker":
            command = f"cd {working_dir} && {flags} 2>&1 | tee {output_file}"
            result = await runtime.run_shell(workspot, command, detached=True)
        else:
            command = f"{flags} 2>&1 | tee {output_file}"
            result = await runtime.run_shell(workspot, command, cwd=working_dir, detached=True)

        if result.returncode != 0:
            err = result.stderr.strip()
            if workspot.container and "No such container" in err:
                return False, f"Container '{workspot.container}' not found."
            return False, err or "Failed to start claude"

        await self.server_manager.ensure_server(workspot)
        return True, ""

    def _session_record(
        self,
        *,
        workspot: Workspot,
        label: str,
        working_dir: str,
        url: str,
        branch: str | None = None,
        worktree_path: str | None = None,
    ) -> SessionRecord:
        return SessionRecord(
            id=secrets.token_urlsafe(8),
            workspot=workspot.name,
            server_key=self.server_manager.server_key(workspot),
            label=label,
            runtime=workspot.runtime,
            container=workspot.container,
            repo_root=workspot.dir,
            working_dir=working_dir,
            branch=branch,
            worktree_path=worktree_path,
            url=url,
            status=SessionStatus.running,
            created_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            source="launcher",
            server_session_name=label,
        )

    async def create_session(self, req: StartRequest) -> dict:
        workspot = self.config.get_workspot(req.workspot)
        if not workspot:
            return {"status": "error", "message": f"Unknown workspot '{req.workspot}'"}

        if req.worktree:
            return await self.create_worktree_session(workspot)

        existing_url = await self.existing_session_url(workspot)
        if existing_url:
            return {"status": "ok", "url": existing_url, "reused": True, "workspot": workspot.name}

        if not await self.server_manager.check_auth(workspot):
            return {"status": "error", "message": "Claude is not authenticated. Run 'claude' interactively first."}

        output_file = self.server_manager.output_file(workspot.name)
        await self._runtime(workspot).run_shell(workspot, f"rm -f {output_file}")

        ok, err = await self.launch_session(workspot, workspot.dir, output_file)
        if not ok:
            return {"status": "error", "message": err}

        url, last_output = await self.poll_for_url(workspot, output_file)
        if not url:
            msg = (
                f"Timed out. Last output:\n{last_output}"
                if last_output
                else "Timed out. No output from claude — check it is installed and authenticated in the container."
            )
            return {"status": "error", "message": msg}

        self.history_store.save_session(url, workspot=workspot.name)
        self.registry.upsert_session(self._session_record(workspot=workspot, label=workspot.name, working_dir=workspot.dir, url=url))
        return {"status": "ok", "url": url, "reused": False, "workspot": workspot.name}

    async def create_worktree_session(self, workspot: Workspot) -> dict:
        if not await self.server_manager.check_auth(workspot):
            return {"status": "error", "message": "Claude is not authenticated. Run 'claude' interactively first."}

        date_str = datetime.utcnow().strftime("%Y%m%d")
        hex_suffix = secrets.token_hex(2)
        branch = f"wt-{date_str}-{hex_suffix}"
        worktree_path = f"/tmp/claude-worktrees/{branch}"
        output_file = f"/tmp/claude-rc-wt-{branch}.txt"

        git_result = await self._runtime(workspot).run_shell(
            workspot,
            f"git -C {workspot.dir} worktree add -b {branch} {worktree_path} 2>&1",
        )
        if git_result.returncode != 0:
            return {
                "status": "error",
                "message": f"Failed to create worktree: {(git_result.stdout + git_result.stderr).strip()}",
            }

        ok, err_msg = await self.launch_session(workspot, worktree_path, output_file)
        if not ok:
            return {"status": "error", "message": err_msg}

        url, last_output = await self.poll_for_url(workspot, output_file)
        if not url:
            msg = (
                f"Timed out. Last output:\n{last_output}"
                if last_output
                else "Timed out. No output from claude — check it is installed and authenticated in the container."
            )
            return {"status": "error", "message": msg}

        self.history_store.save_session(url, workspot=workspot.name, worktree=branch)
        self.registry.upsert_session(
            self._session_record(
                workspot=workspot,
                label=branch,
                working_dir=worktree_path,
                url=url,
                branch=branch,
                worktree_path=worktree_path,
            )
        )
        return {"status": "ok", "url": url, "worktree": branch, "reused": False, "workspot": workspot.name}

    async def kill_workspot(self, workspot: Workspot) -> dict:
        await self.server_manager.stop_server(workspot)
        state = self.registry.load()
        now = datetime.now(timezone.utc)
        changed = False
        for index, session in enumerate(state.sessions):
            if session.workspot == workspot.name and session.status in {SessionStatus.pending, SessionStatus.running}:
                state.sessions[index] = session.model_copy(update={"status": SessionStatus.stopped, "last_seen_at": now})
                changed = True
        if changed:
            self.registry.save(state)
        return {"status": "ok"}
