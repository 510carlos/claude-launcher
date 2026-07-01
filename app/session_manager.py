from __future__ import annotations

import asyncio
import json
import re
import secrets
import shlex
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import logging

from app.models import ResumeRequest, RuntimeType, SessionRecord, SessionStatus, StartRequest, Workspot
from app.registry import SessionHistoryStore, SessionRegistry
from app.runtime import RuntimeManager
from app.server_manager import ServerManager

log = logging.getLogger(__name__)

ERROR_PATTERNS = ["not trusted", "not authenticated", "no such container", "error:", "permission denied", "command not found", "too old for remote control"]


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

    @staticmethod
    def _resolve_devcontainer_workspace(host_dir: str) -> str | None:
        """Read workspaceFolder from devcontainer.json."""
        dc_config = Path(host_dir) / ".devcontainer" / "devcontainer.json"
        if not dc_config.exists():
            return None
        try:
            raw = dc_config.read_text()
            cleaned = re.sub(r'//.*$', '', raw, flags=re.MULTILINE)
            cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
            data = json.loads(cleaned)
            return data.get("workspaceFolder")
        except Exception:
            return None

    def resolve_workspot(self, name: str) -> Workspot | None:
        if self._workspot_resolver:
            return self._workspot_resolver(name)
        return self.config.get_workspot(name)

    def _runtime(self, workspot: Workspot):
        return self.runtime_manager.for_workspot(workspot)

    def output_file(self, session_id: str) -> str:
        return f"/tmp/claude-rc-session-{session_id}.txt"

    def _use_tmux(self, workspot: Workspot) -> bool:
        """tmux hosting applies only to host-runtime workspots, when enabled."""
        return self.config.tmux_host and workspot.runtime == RuntimeType.host

    @staticmethod
    def _tmux_name(session_id: str) -> str:
        return f"claunch-{session_id}"

    def _attach_command(self, tmux_name: str) -> str:
        """The copy-able command the UI shows for reattaching from a desktop terminal."""
        if self.config.tmux_ssh_host:
            return f"ssh {self.config.tmux_ssh_host} -t tmux attach -t {tmux_name}"
        return f"tmux attach -t {tmux_name}"

    async def _capture_output(self, workspot: Workspot, *, output_file: str | None, tmux_session: str | None) -> str:
        """Read a session's current output — from the tmux pane if hosted there, else the tee'd file."""
        runtime = self._runtime(workspot)
        if tmux_session:
            result = await runtime.run_shell(workspot, f"tmux capture-pane -t {tmux_session} -p -S -500 2>/dev/null")
        elif output_file:
            result = await runtime.run_shell(workspot, f"test -f {output_file} && cat {output_file}")
        else:
            return ""
        return result.stdout if result.returncode == 0 else ""

    def derive_label(self, workspot: Workspot, *, label: str | None = None, branch: str | None = None, directory: str | None = None) -> str:
        if label:
            return label
        # Build a descriptive name for the Claude app: "Machine · branch [· Docker]"
        machine = self.config.app_name or "Host"
        parts = [machine]
        if branch:
            parts.append(branch)
        if workspot.runtime.value == "docker":
            parts.append("Docker")
        elif workspot.runtime.value == "devcontainer":
            parts.append("Dev")
        return " · ".join(parts)

    async def poll_for_url(self, workspot: Workspot, output_file: str, *, timeout: float | None = None, tmux_session: str | None = None) -> tuple[str | None, str]:
        deadline = time.monotonic() + (timeout if timeout is not None else self.config.url_capture_timeout)
        last_output = ""
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            output = await self._capture_output(workspot, output_file=output_file, tmux_session=tmux_session)
            if output:
                last_output = output.strip()
                match = re.search(r"https://claude\.ai/code\S+", output)
                if match:
                    return match.group(0), last_output
        return None, last_output

    async def _transcript_size_mb(self, workspot: Workspot, working_dir: str, conversation_id: str) -> float | None:
        """Best-effort size (MB) of a conversation transcript on the runtime, used to scale the resume timeout.

        Returns None if the file can't be found/stat'd; callers fall back to the base timeout.
        """
        slug = "-" + working_dir.lstrip("/").replace("/", "-")
        path = f"$HOME/.claude/projects/{slug}/{conversation_id}.jsonl"
        runtime = self._runtime(workspot)
        result = await runtime.run_shell(workspot, f'stat -c %s "{path}" 2>/dev/null')
        if result.returncode != 0:
            return None
        try:
            return int(result.stdout.strip()) / (1024 * 1024)
        except (ValueError, TypeError):
            return None

    def _resume_timeout(self, size_mb: float | None) -> int:
        """Scale the URL-capture timeout to transcript size: forking a large transcript is slow."""
        base = self.config.resume_url_capture_base
        if size_mb is None:
            return base
        scaled = base + self.config.resume_url_capture_per_mb * size_mb
        return int(min(self.config.resume_url_capture_max, max(base, scaled)))

    async def ensure_workspace_trusted(self, workspot: Workspot, directory: str) -> None:
        """Ensure the workspace directory is trusted in ~/.claude.json so remote-control doesn't prompt."""
        runtime = self._runtime(workspot)
        # Use python3 to atomically read-modify-write ~/.claude.json
        script = (
            "import json, os, pathlib; "
            "p = pathlib.Path(os.path.expanduser('~/.claude.json')); "
            "data = json.loads(p.read_text()) if p.exists() else {}; "
            "projects = data.setdefault('projects', {}); "
            f"proj = projects.setdefault({directory!r}, {{}}); "
            "changed = not proj.get('hasTrustDialogAccepted'); "
            "proj['hasTrustDialogAccepted'] = True; "
            "p.write_text(json.dumps(data, indent=2)) if changed else None; "
            "print('trusted' if changed else 'already trusted')"
        )
        result = await runtime.run_shell(workspot, f'python3 -c "{script}"')
        if result.returncode == 0:
            log.info("Workspace trust for %s: %s", directory, result.stdout.strip())
        else:
            log.warning("Failed to set workspace trust for %s: %s", directory, result.stderr.strip())

    async def ensure_auto_approve(self, workspot: Workspot, directory: str) -> None:
        """Ensure .claude/settings.json in the workspace has a PermissionRequest hook to auto-approve tools."""
        import base64

        runtime = self._runtime(workspot)
        settings_path = f"{directory}/.claude/settings.json"

        # Read existing settings from the workspace
        result = await runtime.run_shell(workspot, f"cat {settings_path} 2>/dev/null")
        try:
            data = json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else {}
        except json.JSONDecodeError:
            data = {}

        hooks = data.setdefault("hooks", {})
        pr = hooks.get("PermissionRequest", [])

        # Check if auto-approve hook already exists
        has_auto = any(
            "allow" in h.get("hooks", [{}])[0].get("command", "")
            for h in pr if h.get("hooks")
        )
        if has_auto:
            log.info("Auto-approve for %s: already set", directory)
            return

        # Build the hook — echo produces the JSON that Claude Code expects
        payload = json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "allow"},
            }
        })
        pr.append({"matcher": "", "hooks": [{"type": "command", "command": f"echo '{payload}'"}]})
        hooks["PermissionRequest"] = pr

        # Write back via base64 to avoid shell quoting issues
        settings_json = json.dumps(data, indent=2)
        b64 = base64.b64encode(settings_json.encode()).decode()
        await runtime.run_shell(workspot, f"mkdir -p {directory}/.claude")
        result = await runtime.run_shell(workspot, f"echo {b64} | base64 -d > {settings_path}")
        if result.returncode == 0:
            log.info("Auto-approve for %s: added", directory)
        else:
            log.warning("Failed to set auto-approve for %s: %s", directory, result.stderr.strip())

    async def launch_session(self, workspot: Workspot, session: SessionRecord, *, spawn_worktree: bool = False) -> tuple[bool, str]:
        runtime = self._runtime(workspot)

        # Auto-trust the workspace directory so remote-control doesn't prompt
        await self.ensure_workspace_trusted(workspot, session.working_dir or workspot.dir)

        # Auto-approve tool permissions so phone doesn't prompt
        await self.ensure_auto_approve(workspot, session.working_dir or workspot.dir)

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
        # Always pass an explicit spawn mode. With a TTY (e.g. running inside tmux)
        # remote-control otherwise prompts "[1/2] same-dir/worktree" and blocks
        # waiting for input — so the URL is never emitted. same-dir is the default.
        spawn_flag = "--spawn worktree" if spawn_worktree else "--spawn same-dir"
        capacity_flag = f"--capacity {workspot.server_capacity}" if workspot.server_capacity != 32 else ""
        flags = " ".join(
            part
            for part in [self.config.claude_global_flags, workspot.claude_bin, "remote-control", name_flag, spawn_flag, capacity_flag, self.config.claude_rc_flags]
            if part
        ).strip()
        tmux_session = session.metadata.get("tmux_session")
        if tmux_session:
            # Run claude directly on the tmux PTY (no tee pipe — that would divert
            # stdout off the terminal and break the attachable TUI). Output is read
            # back via `tmux capture-pane`.
            inner = f"{env_prefix} {flags}".strip()
            cwd = session.working_dir or workspot.dir
            command = f"tmux new-session -d -s {tmux_session} -c {shlex.quote(cwd)} {shlex.quote(inner)}"
            result = await runtime.run_shell(workspot, command)
        else:
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
        metadata: dict = {}
        if self._use_tmux(workspot):
            tmux_name = self._tmux_name(session_id)
            metadata["tmux_session"] = tmux_name
            metadata["attach_command"] = self._attach_command(tmux_name)
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
            metadata=metadata,
        )

    async def create_session(self, req: StartRequest) -> dict:
        workspot = self.resolve_workspot(req.workspot)
        if not workspot:
            return {"status": "error", "message": f"Unknown workspot '{req.workspot}'"}

        # For devcontainer launches, create a temporary workspot override
        effective_workspot = workspot
        if req.devcontainer:
            # Start devcontainer if not running
            dc_adapter = self.runtime_manager.devcontainer
            if not await dc_adapter.is_running(workspot.dir):
                log.info("Starting devcontainer for %s...", workspot.name)
                up_result = await dc_adapter.up(workspot.dir)
                if up_result.returncode != 0:
                    return {"status": "error", "message": f"Failed to start devcontainer: {up_result.stderr.strip()[:200]}"}

            # Resolve workspace folder inside container
            from app.models import RuntimeType
            dc_workspace = self._resolve_devcontainer_workspace(workspot.dir)
            effective_workspot = workspot.model_copy(update={
                "runtime": RuntimeType.devcontainer,
                "dir": dc_workspace or workspot.dir,
            })

        # Pre-flight checks (skip for devcontainer — we just verified it's up)
        if not req.devcontainer:
            issues = await self.server_manager.check_preflight(workspot)
            if issues:
                return {"status": "error", "message": "Pre-flight failed: " + "; ".join(issues)}

        working_dir = req.directory or effective_workspot.dir

        # Auto-detect git branch if not explicitly provided
        branch = req.branch
        if not branch:
            runtime = self._runtime(effective_workspot)
            br_result = await runtime.run_shell(
                effective_workspot, f"git -C {working_dir} symbolic-ref --short HEAD 2>/dev/null"
            )
            if br_result.returncode == 0 and br_result.stdout.strip():
                branch = br_result.stdout.strip()

        label = self.derive_label(workspot, label=req.label, branch=branch, directory=working_dir)
        if req.worktree and not req.label:
            # Make worktree sessions clearly distinguishable
            repo = PurePosixPath(workspot.dir).name
            suffix = req.branch or f"wt-{secrets.token_hex(2)}"
            label = f"{repo}/{suffix}"

        session_id = secrets.token_urlsafe(8)
        record = self.build_session_record(
            session_id=session_id,
            workspot=effective_workspot,
            label=label,
            working_dir=working_dir,
            branch=branch,
        )
        self.registry.upsert_session(record)

        ok, err = await self.launch_session(effective_workspot, record, spawn_worktree=req.worktree)
        if not ok:
            self.registry.mark_session(session_id, status=SessionStatus.failed, metadata={"error": err})
            return {"status": "error", "message": err}

        url, last_output = await self.poll_for_url(workspot, record.output_file or "", tmux_session=record.metadata.get("tmux_session"))
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

    async def launch_resume(self, workspot: Workspot, session: SessionRecord, conversation_id: str) -> tuple[bool, str]:
        runtime = self._runtime(workspot)

        await self.ensure_workspace_trusted(workspot, session.working_dir or workspot.dir)
        await self.ensure_auto_approve(workspot, session.working_dir or workspot.dir)

        env_vars = {
            "CLAUDE_LAUNCHER_SESSION_ID": session.id,
            "CLAUDE_LAUNCHER_WORKSPOT": workspot.name,
            "CLAUDE_LAUNCHER_LABEL": session.label,
            "CLAUDE_LAUNCHER_BRANCH": session.branch or "",
            "CLAUDE_LAUNCHER_OUTPUT_FILE": session.output_file or "",
        }
        env_prefix = " ".join(f'{key}="{value}"' for key, value in env_vars.items() if value is not None)
        name_flag = f'--name "{session.label}"' if session.label else ""
        flags = " ".join(
            part
            for part in [
                self.config.claude_global_flags,
                workspot.claude_bin,
                "--resume", conversation_id,
                "--remote-control",
                "--fork-session",
                name_flag,
                self.config.claude_rc_flags,
            ]
            if part
        ).strip()
        tmux_session = session.metadata.get("tmux_session")
        if tmux_session:
            inner = f"{env_prefix} {flags}".strip()
            cwd = session.working_dir or workspot.dir
            command = f"tmux new-session -d -s {tmux_session} -c {shlex.quote(cwd)} {shlex.quote(inner)}"
            result = await runtime.run_shell(workspot, command)
        else:
            command = f"{env_prefix} {flags} 2>&1 | tee {session.output_file}".strip()
            result = await runtime.run_shell(workspot, command, cwd=session.working_dir, detached=True)

        if result.returncode != 0:
            err = result.stderr.strip()
            if workspot.container and "No such container" in err:
                return False, f"Container '{workspot.container}' not found."
            return False, err or "Failed to start claude --resume"

        await self.server_manager.ensure_server(workspot)
        return True, ""

    async def resume_session(self, req: ResumeRequest) -> dict:
        """Resume a previous Claude conversation via `claude --resume <id> --remote-control --fork-session`."""
        workspot = self.resolve_workspot(req.workspot)
        if not workspot:
            return {"status": "error", "message": f"Unknown workspot '{req.workspot}'"}

        issues = await self.server_manager.check_preflight(workspot)
        if issues:
            return {"status": "error", "message": "Pre-flight failed: " + "; ".join(issues)}

        label = req.label or f"resume-{req.conversation_id[:8]}"
        session_id = secrets.token_urlsafe(8)
        record = self.build_session_record(
            session_id=session_id,
            workspot=workspot,
            label=label,
            working_dir=workspot.dir,
            source="resume",
        )
        self.registry.upsert_session(record)

        ok, err = await self.launch_resume(workspot, record, req.conversation_id)
        if not ok:
            self.registry.mark_session(session_id, status=SessionStatus.failed, metadata={"error": err, "resumed_from": req.conversation_id})
            return {"status": "error", "message": err}

        size_mb = await self._transcript_size_mb(workspot, record.working_dir or workspot.dir, req.conversation_id)
        resume_timeout = self._resume_timeout(size_mb)
        log.info("Resuming %s: transcript=%.1fMB, url-capture timeout=%ds", req.conversation_id, size_mb or 0.0, resume_timeout)
        url, last_output = await self.poll_for_url(workspot, record.output_file or "", timeout=resume_timeout, tmux_session=record.metadata.get("tmux_session"))
        if not url:
            is_error = any(p in last_output.lower() for p in ERROR_PATTERNS)
            new_status = SessionStatus.failed if is_error else SessionStatus.pending
            error_msg = last_output.strip().split("\n")[-1] if is_error else None
            self.registry.mark_session(session_id, status=new_status, metadata={"last_output": last_output, "error": error_msg, "resumed_from": req.conversation_id})
            if is_error:
                return {"status": "error", "message": f"Resume failed: {error_msg}", "session_id": session_id}
            return {
                "status": "ok",
                "session": self.registry.get_session(session_id).model_dump(mode="json"),
                "pending_url": True,
                "message": "Resume started. Waiting for URL callback or output capture.",
            }

        updated = self.registry.mark_session(
            session_id,
            status=SessionStatus.running,
            url=url,
            metadata={"last_output": last_output, "resumed_from": req.conversation_id},
        )
        self.history_store.save_session(url, workspot=workspot.name, label=label)
        return {"status": "ok", "session": updated.model_dump(mode="json"), "url": url, "resumed": True, "workspot": workspot.name}

    async def kill_session(self, session_id: str) -> dict:
        session = self.registry.get_session(session_id)
        if not session:
            return {"status": "error", "message": f"Unknown session '{session_id}'"}
        workspot = self.resolve_workspot(session.workspot)
        if not workspot:
            return {"status": "error", "message": f"Unknown workspot '{session.workspot}'"}

        runtime = self._runtime(workspot)

        # Kill the session by process group. Only the launch wrapper carries
        # CLAUDE_LAUNCHER_SESSION_ID in its argv; the `claude` child's argv is just
        # `claude remote-control --name ...`, so a plain `pgrep | kill` matches the
        # wrapper but orphans claude. Each launch runs under its own session/group
        # (setsid / tmux pane), so signalling the wrapper's process group (kill -PGID)
        # takes down claude and the tee too.
        kill_pattern = f'CLAUDE_LAUNCHER_SESSION_ID="{session_id}"'
        # `pgrep -f` also matches this very kill command (the pattern is in its argv),
        # and that self-match shell shares the launcher's own process group — so we
        # must never group-kill our own group or we'd take down the service. The real
        # session wrapper runs under its own group (setsid / tmux pane), so skipping
        # $self_pgid kills the session while sparing the launcher and the matcher.
        kill_group = (
            f'self_pgid=$(ps -o pgid= -p $$ | tr -d " "); '
            f"pgrep -f '{kill_pattern}' | while read pid; do "
            f'pgid=$(ps -o pgid= -p "$pid" | tr -d " "); '
            f'[ -n "$pgid" ] && [ "$pgid" != "$self_pgid" ] && kill -{{sig}} -"$pgid" 2>/dev/null; '
            f"done"
        )
        # Graceful SIGTERM so Claude can clean up worktrees, then force-kill stragglers.
        await runtime.run_shell(workspot, kill_group.format(sig="TERM"))
        await asyncio.sleep(2)
        await runtime.run_shell(workspot, kill_group.format(sig="KILL"))

        # Tear down the tmux session (usually already gone once claude exits, but
        # kill it explicitly to clean up any leftover empty session).
        tmux_session = session.metadata.get("tmux_session")
        if tmux_session:
            await runtime.run_shell(workspot, f"tmux kill-session -t {tmux_session} 2>/dev/null || true")

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
        tmux_session = session.metadata.get("tmux_session")
        if not session.output_file and not tmux_session:
            return {"status": "ok", "output": "", "lines": 0}
        workspot = self.resolve_workspot(session.workspot)
        if not workspot:
            return {"status": "error", "message": f"Unknown workspot '{session.workspot}'"}
        raw = await self._capture_output(workspot, output_file=session.output_file, tmux_session=tmux_session)
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw)
        clean = re.sub(r'\x1b\]8;;[^\x07]*\x07', '', clean)  # strip hyperlink escapes
        lines = [ln for ln in clean.strip().split('\n')] if clean.strip() else []
        lines = lines[-tail:]
        return {"status": "ok", "output": "\n".join(lines), "lines": len(lines)}

    async def reconcile_sessions(self) -> int:
        """Check pending/running sessions and update their status. Returns count of updates."""
        updated = 0
        for session in self.registry.list_sessions():
            if session.status == SessionStatus.pending:
                workspot = self.resolve_workspot(session.workspot)
                if not workspot or not session.output_file:
                    continue
                runtime = self._runtime(workspot)
                output = (await self._capture_output(workspot, output_file=session.output_file, tmux_session=session.metadata.get("tmux_session"))).strip()
                if not output:
                    continue
                # Check for URL → promote to running
                match = re.search(r"https://claude\.ai/code\S+", output)
                if match:
                    self.registry.mark_session(session.id, status=SessionStatus.running, url=match.group(0))
                    updated += 1
                    continue
                # Check for errors → mark failed, but only once the process is actually gone.
                # A long resume fork can emit error-like text mid-stream while still working;
                # failing it while claude is alive would abort a healthy (slow) resume.
                if any(p in output.lower() for p in ERROR_PATTERNS):
                    proc_check = await runtime.run_shell(workspot, f"pgrep -f 'CLAUDE_LAUNCHER_SESSION_ID=\"{session.id}\"'")
                    if proc_check.returncode == 0:
                        continue  # still running — leave pending, give it time
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
