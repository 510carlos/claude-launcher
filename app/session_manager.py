from __future__ import annotations

import asyncio
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath

import logging

from app.models import SessionRecord, SessionStatus, StartRequest, Workspot
from app.registry import SessionHistoryStore, SessionRegistry
from app.runtime import RuntimeManager
from app.server_manager import ServerManager

log = logging.getLogger(__name__)

ERROR_PATTERNS = ["not trusted", "not authenticated", "no such container", "error:", "permission denied", "command not found"]


class SessionManager:
    def __init__(
        self,
        *,
        config,
        registry: SessionRegistry,
        history_store: SessionHistoryStore,
        runtime_manager: RuntimeManager,
        server_manager: ServerManager,
        workspot_resolver=None,
    ):
        self.config = config
        self.registry = registry
        self.history_store = history_store
        self.runtime_manager = runtime_manager
        self.server_manager = server_manager
        self._workspot_resolver = workspot_resolver

    def resolve_workspot(self, name: str) -> Workspot | None:
        if self._workspot_resolver:
            return self._workspot_resolver(name)
        return self.config.get_workspot(name)

    def _runtime(self, workspot: Workspot):
        return self.runtime_manager.for_workspot(workspot)

    def output_file(self, session_id: str) -> str:
        return f"/tmp/claude-rc-session-{session_id}.txt"

    def derive_label(self, workspot: Workspot, *, label: str | None = None, branch: str | None = None, directory: str | None = None) -> str:
        if label:
            return label
        if branch:
            repo = PurePosixPath(workspot.dir).name
            return f"{repo}/{branch}"
        if directory:
            name = PurePosixPath(directory).name
            if name:
                return name
        # Use repo name + short timestamp for unique, readable names
        repo = PurePosixPath(workspot.dir).name
        ts = datetime.now(timezone.utc).strftime("%H%M")
        return f"{repo}-{ts}-{secrets.token_hex(1)}"

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

    async def launch_session(self, workspot: Workspot, session: SessionRecord, *, spawn_worktree: bool = False) -> tuple[bool, str]:
        runtime = self._runtime(workspot)

        # For worktree sessions, checkout main first so worktrees branch off main
        if spawn_worktree:
            await runtime.run_shell(workspot, f"git -C {workspot.dir} checkout main 2>/dev/null || git -C {workspot.dir} checkout master 2>/dev/null || true")

        env_vars = {
            "CLAUDE_LAUNCHER_SESSION_ID": session.id,
            "CLAUDE_LAUNCHER_WORKSPOT": workspot.name,
            "CLAUDE_LAUNCHER_LABEL": session.label,
            "CLAUDE_LAUNCHER_BRANCH": session.branch or "",
            "CLAUDE_LAUNCHER_OUTPUT_FILE": session.output_file or "",
        }
        env_prefix = " ".join(f'{key}="{value}"' for key, value in env_vars.items() if value is not None)
        name_flag = f'--name "{session.label}"' if session.label else ""
        spawn_flag = "--spawn worktree" if spawn_worktree else ""
        capacity_flag = f"--capacity {workspot.server_capacity}" if workspot.server_capacity != 32 else ""
        flags = " ".join(
            part
            for part in [self.config.claude_global_flags, workspot.claude_bin, "remote-control", name_flag, spawn_flag, capacity_flag, self.config.claude_rc_flags]
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
        workspot = self.resolve_workspot(req.workspot)
        if not workspot:
            return {"status": "error", "message": f"Unknown workspot '{req.workspot}'"}

        # Pre-flight checks
        issues = await self.server_manager.check_preflight(workspot)
        if issues:
            return {"status": "error", "message": "Pre-flight failed: " + "; ".join(issues)}

        working_dir = req.directory or workspot.dir
        label = self.derive_label(workspot, label=req.label, branch=req.branch, directory=working_dir)
        if req.worktree and not req.label:
            # Make worktree sessions clearly distinguishable
            repo = PurePosixPath(workspot.dir).name
            suffix = req.branch or f"wt-{secrets.token_hex(2)}"
            label = f"{repo}/{suffix}"

        session_id = secrets.token_urlsafe(8)
        record = self.build_session_record(
            session_id=session_id,
            workspot=workspot,
            label=label,
            working_dir=working_dir,
            branch=req.branch,
        )
        self.registry.upsert_session(record)

        ok, err = await self.launch_session(workspot, record, spawn_worktree=req.worktree)
        if not ok:
            self.registry.mark_session(session_id, status=SessionStatus.failed, metadata={"error": err})
            return {"status": "error", "message": err}

        url, last_output = await self.poll_for_url(workspot, record.output_file or "")
        if not url:
            # Check if the output contains errors — mark failed instead of pending
            is_error = any(p in last_output.lower() for p in ERROR_PATTERNS)
            new_status = SessionStatus.failed if is_error else SessionStatus.pending
            error_msg = last_output.strip().split("\n")[-1] if is_error else None
            self.registry.mark_session(session_id, status=new_status, metadata={"last_output": last_output, "error": error_msg})
            if is_error:
                return {"status": "error", "message": f"Session failed: {error_msg}", "session_id": session_id}
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

    async def kill_session(self, session_id: str) -> dict:
        session = self.registry.get_session(session_id)
        if not session:
            return {"status": "error", "message": f"Unknown session '{session_id}'"}
        workspot = self.resolve_workspot(session.workspot)
        if not workspot:
            return {"status": "error", "message": f"Unknown workspot '{session.workspot}'"}

        runtime = self._runtime(workspot)

        # Kill the actual claude remote-control process via session ID in cmdline
        kill_pattern = f'CLAUDE_LAUNCHER_SESSION_ID="{session_id}"'
        await runtime.run_shell(workspot, f"pgrep -f '{kill_pattern}' | xargs -r kill")
        # Give Claude time to clean up worktrees gracefully (SIGTERM)
        await asyncio.sleep(2)
        # Force kill any stragglers
        await runtime.run_shell(workspot, f"pgrep -f '{kill_pattern}' | xargs -r kill -9")

        if session.output_file:
            await runtime.run_shell(workspot, f"rm -f {session.output_file}")
        self.registry.mark_session(session_id, status=SessionStatus.stopped)
        return {"status": "ok", "session_id": session_id}

    async def kill_workspot(self, workspot: Workspot) -> dict:
        await self.server_manager.stop_server(workspot)
        for session in self.registry.list_sessions(workspot=workspot.name):
            if session.status in {SessionStatus.pending, SessionStatus.running}:
                self.registry.mark_session(session.id, status=SessionStatus.stopped)
        return {"status": "ok"}

    async def get_session_output(self, session_id: str, tail: int = 50) -> dict:
        session = self.registry.get_session(session_id)
        if not session:
            return {"status": "error", "message": f"Unknown session '{session_id}'"}
        if not session.output_file:
            return {"status": "ok", "output": "", "lines": 0}
        workspot = self.resolve_workspot(session.workspot)
        if not workspot:
            return {"status": "error", "message": f"Unknown workspot '{session.workspot}'"}
        runtime = self._runtime(workspot)
        result = await runtime.run_shell(workspot, f"tail -n {tail} {session.output_file} 2>/dev/null || echo ''")
        raw = result.stdout if result.returncode == 0 else ""
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw)
        clean = re.sub(r'\x1b\]8;;[^\x07]*\x07', '', clean)  # strip hyperlink escapes
        lines = clean.strip().split('\n') if clean.strip() else []
        return {"status": "ok", "output": clean.strip(), "lines": len(lines)}

    async def reconcile_sessions(self) -> int:
        """Check pending/running sessions and update their status. Returns count of updates."""
        updated = 0
        for session in self.registry.list_sessions():
            if session.status == SessionStatus.pending:
                workspot = self.resolve_workspot(session.workspot)
                if not workspot or not session.output_file:
                    continue
                runtime = self._runtime(workspot)
                result = await runtime.run_shell(workspot, f"cat {session.output_file} 2>/dev/null")
                if result.returncode != 0 or not result.stdout.strip():
                    continue
                output = result.stdout.strip()
                # Check for URL → promote to running
                match = re.search(r"https://claude\.ai/code\S+", output)
                if match:
                    self.registry.mark_session(session.id, status=SessionStatus.running, url=match.group(0))
                    updated += 1
                    continue
                # Check for errors → mark failed
                if any(p in output.lower() for p in ERROR_PATTERNS):
                    error_msg = output.strip().split("\n")[-1]
                    self.registry.mark_session(session.id, status=SessionStatus.failed, metadata={"error": error_msg})
                    updated += 1

            elif session.status == SessionStatus.running:
                workspot = self.resolve_workspot(session.workspot)
                if not workspot:
                    continue
                runtime = self._runtime(workspot)
                proc_check = await runtime.run_shell(workspot, f"pgrep -f 'CLAUDE_LAUNCHER_SESSION_ID=\"{session.id}\"'")
                if proc_check.returncode != 0:
                    self.registry.mark_session(session.id, status=SessionStatus.stopped)
                    updated += 1

        return updated
