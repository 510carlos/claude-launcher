from __future__ import annotations

import asyncio
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath

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

    def output_file(self, session_id: str) -> str:
        return f"/tmp/claude-rc-session-{session_id}.txt"

    def derive_label(self, workspot: Workspot, *, label: str | None = None, branch: str | None = None, directory: str | None = None) -> str:
        if label:
            return label
        if branch:
            return branch
        if directory:
            name = PurePosixPath(directory).name
            if name:
                return name
        return f"{workspot.name}-{secrets.token_hex(2)}"

    async def poll_for_url(self, workspot: Workspot, output_file: str) -> tuple[str | None, str]:
        runtime = self._runtime(workspot)
        deadline = time.monotonic() + self.config.url_capture_timeout
        last_output = ""
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            result = await runtime.run_shell(workspot, f"test -f {output_file} && cat {output_file}")
            if result.returncode == 0:
                last_output = result.stdout.strip()
                match = re.search(r"https://claude\.ai/code\S+", result.stdout)
                if match:
                    return match.group(0), last_output
        return None, last_output

    async def launch_session(self, workspot: Workspot, session: SessionRecord) -> tuple[bool, str]:
        runtime = self._runtime(workspot)
        env_vars = {
            "CLAUDE_LAUNCHER_SESSION_ID": session.id,
            "CLAUDE_LAUNCHER_WORKSPOT": workspot.name,
            "CLAUDE_LAUNCHER_LABEL": session.label,
            "CLAUDE_LAUNCHER_BRANCH": session.branch or "",
            "CLAUDE_LAUNCHER_OUTPUT_FILE": session.output_file or "",
        }
        env_prefix = " ".join(f'{key}="{value}"' for key, value in env_vars.items() if value is not None)
        flags = " ".join(
            part
            for part in [self.config.claude_global_flags, workspot.claude_bin, "remote-control", self.config.claude_rc_flags]
            if part
        ).strip()
        command = f"{env_prefix} {flags} 2>&1 | tee {session.output_file}".strip()
        result = await runtime.run_shell(workspot, command, cwd=session.working_dir, detached=True)

        if result.returncode != 0:
            err = result.stderr.strip()
            if workspot.container and "No such container" in err:
                return False, f"Container '{workspot.container}' not found."
            return False, err or "Failed to start claude"

        await self.server_manager.ensure_server(workspot)
        return True, ""

    def build_session_record(
        self,
        *,
        session_id: str,
        workspot: Workspot,
        label: str,
        working_dir: str,
        branch: str | None = None,
        worktree_path: str | None = None,
        source: str = "launcher",
    ) -> SessionRecord:
        now = datetime.now(timezone.utc)
        return SessionRecord(
            id=session_id,
            workspot=workspot.name,
            server_key=self.server_manager.server_key(workspot),
            label=label,
            runtime=workspot.runtime,
            container=workspot.container,
            repo_root=workspot.dir,
            working_dir=working_dir,
            branch=branch,
            worktree_path=worktree_path,
            status=SessionStatus.pending,
            created_at=now,
            last_seen_at=now,
            source=source,
            server_session_name=label,
            output_file=self.output_file(session_id),
        )

    async def create_session(self, req: StartRequest) -> dict:
        workspot = self.config.get_workspot(req.workspot)
        if not workspot:
            return {"status": "error", "message": f"Unknown workspot '{req.workspot}'"}

        if req.worktree:
            return await self.create_worktree_session(workspot, req)

        if not await self.server_manager.check_auth(workspot):
            return {"status": "error", "message": "Claude is not authenticated. Run 'claude' interactively first."}

        working_dir = req.directory or workspot.dir
        label = self.derive_label(workspot, label=req.label, branch=req.branch, directory=working_dir)
        session_id = secrets.token_urlsafe(8)
        record = self.build_session_record(
            session_id=session_id,
            workspot=workspot,
            label=label,
            working_dir=working_dir,
            branch=req.branch,
        )
        self.registry.upsert_session(record)

        ok, err = await self.launch_session(workspot, record)
        if not ok:
            self.registry.mark_session(session_id, status=SessionStatus.failed, metadata={"error": err})
            return {"status": "error", "message": err}

        url, last_output = await self.poll_for_url(workspot, record.output_file or "")
        if not url:
            self.registry.mark_session(session_id, status=SessionStatus.pending, metadata={"last_output": last_output})
            return {
                "status": "ok",
                "session": self.registry.get_session(session_id).model_dump(mode="json"),
                "pending_url": True,
                "message": "Session started. Waiting for URL callback or output capture.",
            }

        updated = self.registry.mark_session(
            session_id,
            status=SessionStatus.running,
            url=url,
            metadata={"last_output": last_output},
        )
        self.history_store.save_session(url, workspot=workspot.name, label=label)
        return {"status": "ok", "session": updated.model_dump(mode="json"), "url": url, "reused": False, "workspot": workspot.name}

    async def create_worktree_session(self, workspot: Workspot, req: StartRequest) -> dict:
        if not await self.server_manager.check_auth(workspot):
            return {"status": "error", "message": "Claude is not authenticated. Run 'claude' interactively first."}

        branch = req.branch or f"wt-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(2)}"
        worktree_path = f"/tmp/claude-worktrees/{branch}"
        git_result = await self._runtime(workspot).run_shell(
            workspot,
            f"git -C {workspot.dir} worktree add -b {branch} {worktree_path} 2>&1",
        )
        if git_result.returncode != 0:
            return {
                "status": "error",
                "message": f"Failed to create worktree: {(git_result.stdout + git_result.stderr).strip()}",
            }

        label = self.derive_label(workspot, label=req.label, branch=branch, directory=worktree_path)
        session_id = secrets.token_urlsafe(8)
        record = self.build_session_record(
            session_id=session_id,
            workspot=workspot,
            label=label,
            working_dir=worktree_path,
            branch=branch,
            worktree_path=worktree_path,
        )
        self.registry.upsert_session(record)

        ok, err_msg = await self.launch_session(workspot, record)
        if not ok:
            self.registry.mark_session(session_id, status=SessionStatus.failed, metadata={"error": err_msg})
            return {"status": "error", "message": err_msg}

        url, last_output = await self.poll_for_url(workspot, record.output_file or "")
        if not url:
            self.registry.mark_session(session_id, status=SessionStatus.pending, metadata={"last_output": last_output})
            return {
                "status": "ok",
                "session": self.registry.get_session(session_id).model_dump(mode="json"),
                "pending_url": True,
                "message": "Worktree session started. Waiting for URL callback or output capture.",
            }

        updated = self.registry.mark_session(
            session_id,
            status=SessionStatus.running,
            url=url,
            branch=branch,
            metadata={"last_output": last_output},
        )
        self.history_store.save_session(url, workspot=workspot.name, worktree=branch, label=label)
        return {
            "status": "ok",
            "session": updated.model_dump(mode="json"),
            "url": url,
            "worktree": branch,
            "reused": False,
            "workspot": workspot.name,
        }

    async def kill_session(self, session_id: str) -> dict:
        session = self.registry.get_session(session_id)
        if not session:
            return {"status": "error", "message": f"Unknown session '{session_id}'"}
        workspot = self.config.get_workspot(session.workspot)
        if not workspot:
            return {"status": "error", "message": f"Unknown workspot '{session.workspot}'"}

        runtime = self._runtime(workspot)
        if session.output_file:
            await runtime.run_shell(workspot, f"rm -f {session.output_file}")
        self.registry.mark_session(session_id, status=SessionStatus.stopped)
        return {"status": "ok", "session_id": session_id}

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
