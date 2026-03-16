from __future__ import annotations

import asyncio
import logging
import re
import secrets
import time
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import load_config
from models import KillRequest, ServerRecord, ServerStatus, SessionRecord, SessionStatus, StartRequest, Workspot
from registry import SessionHistoryStore, SessionRegistry
from runtime import RuntimeManager

config = load_config()
registry = SessionRegistry(config.session_registry_file)
history_store = SessionHistoryStore(config.session_history_file, max_sessions=config.max_sessions)
runtime_manager = RuntimeManager(local_env=config.local_claude_env)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


def _server_key(workspot: Workspot) -> str:
    return workspot.name


def _output_file(workspot_name: str) -> str:
    return f"/tmp/claude-rc-{workspot_name}.txt"


def _runtime(workspot: Workspot):
    return runtime_manager.for_workspot(workspot)


def _build_server_record(workspot: Workspot, *, status: ServerStatus, log_file: str | None = None) -> ServerRecord:
    now = datetime.now(timezone.utc)
    return ServerRecord(
        workspot=workspot.name,
        server_key=_server_key(workspot),
        runtime=workspot.runtime,
        container=workspot.container,
        status=status,
        capacity=workspot.server_capacity,
        last_seen_at=now,
        started_at=now if status == ServerStatus.running else None,
        log_file=log_file,
    )


@app.on_event("startup")
async def check_ts_key_expiry():
    if not config.ts_key_expires:
        return
    try:
        expiry = datetime.fromisoformat(config.ts_key_expires).replace(tzinfo=timezone.utc)
        days_left = (expiry - datetime.now(timezone.utc)).days
        if days_left <= 14:
            log.warning(
                "Tailscale auth key expires in %d day(s) (%s). Rotate soon!",
                days_left,
                config.ts_key_expires,
            )
    except ValueError:
        log.warning("TS_KEY_EXPIRES '%s' is not a valid ISO date, skipping check.", config.ts_key_expires)


async def check_claude_auth(workspot: Workspot) -> bool:
    runtime = _runtime(workspot)
    creds = "/home/node/.claude/.credentials.json" if workspot.runtime.value == "docker" else "/home/claude-config/.claude/.credentials.json"
    result = await runtime.run_shell(workspot, f"test -s {creds} && echo ok")
    return result.returncode == 0 and "ok" in result.stdout


async def is_session_running(workspot: Workspot) -> str | None:
    runtime = _runtime(workspot)
    output_file = _output_file(workspot.name)

    proc_check = await runtime.run(workspot, ["pgrep", "-f", "claude remote-control"])
    if proc_check.returncode != 0:
        registry.upsert_server(_build_server_record(workspot, status=ServerStatus.stopped, log_file=output_file))
        return None

    output = await runtime.run(workspot, ["cat", output_file])
    if output.returncode == 0:
        match = re.search(r"https://claude\.ai/code\S+", output.stdout)
        if match:
            registry.upsert_server(_build_server_record(workspot, status=ServerStatus.running, log_file=output_file))
            return match.group(0)

    await kill_session(workspot)
    registry.upsert_server(_build_server_record(workspot, status=ServerStatus.unhealthy, log_file=output_file))
    return None


async def kill_session(workspot: Workspot):
    runtime = _runtime(workspot)
    await runtime.run_shell(workspot, "pgrep -f 'claude remote-control' | xargs -r kill")


async def poll_for_url(workspot: Workspot, output_file: str) -> tuple[str | None, str]:
    runtime = _runtime(workspot)
    deadline = time.monotonic() + config.url_capture_timeout
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


async def launch_session(workspot: Workspot, working_dir: str, output_file: str) -> tuple[bool, str]:
    runtime = _runtime(workspot)
    flags = " ".join(part for part in [config.claude_global_flags, workspot.claude_bin, "remote-control", config.claude_rc_flags] if part).strip()
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

    registry.upsert_server(_build_server_record(workspot, status=ServerStatus.running, log_file=output_file))
    return True, ""


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/workspots")
async def list_workspots():
    return JSONResponse([{ 
        "name": w.name,
        "runtime": w.runtime.value,
        "container": w.container,
        "dir": w.dir,
        "server_capacity": w.server_capacity,
    } for w in config.workspots])


@app.get("/sessions")
async def get_sessions():
    return JSONResponse(history_store.load())


@app.get("/status")
async def get_status():
    results = await asyncio.gather(*[is_session_running(ws) for ws in config.workspots])
    return JSONResponse([
        {"name": ws.name, "running": url is not None, "url": url}
        for ws, url in zip(config.workspots, results)
    ])


@app.post("/kill")
async def kill_session_endpoint(req: KillRequest):
    ws = config.get_workspot(req.workspot)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{req.workspot}'"})
    await kill_session(ws)
    await _runtime(ws).run_shell(ws, f"rm -f {_output_file(ws.name)}")
    registry.upsert_server(_build_server_record(ws, status=ServerStatus.stopped, log_file=_output_file(ws.name)))
    return JSONResponse({"status": "ok"})


@app.post("/start")
async def start_session(req: StartRequest):
    ws = config.get_workspot(req.workspot)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{req.workspot}'"})

    existing_url = await is_session_running(ws)
    if existing_url:
        return JSONResponse({"status": "ok", "url": existing_url, "reused": True, "workspot": ws.name})

    if not await check_claude_auth(ws):
        return JSONResponse({
            "status": "error",
            "message": "Claude is not authenticated. Run 'claude' interactively first.",
        })

    output_file = _output_file(ws.name)
    await _runtime(ws).run_shell(ws, f"rm -f {output_file}")

    ok, err = await launch_session(ws, ws.dir, output_file)
    if not ok:
        return JSONResponse({"status": "error", "message": err})

    url, last_output = await poll_for_url(ws, output_file)
    if url:
        history_store.save_session(url, workspot=ws.name)
        registry.upsert_session(SessionRecord(
            id=secrets.token_urlsafe(8),
            workspot=ws.name,
            server_key=_server_key(ws),
            label=ws.name,
            runtime=ws.runtime,
            container=ws.container,
            repo_root=ws.dir,
            working_dir=ws.dir,
            url=url,
            status=SessionStatus.running,
            created_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            source="launcher",
            server_session_name=ws.name,
        ))
        return JSONResponse({"status": "ok", "url": url, "reused": False, "workspot": ws.name})

    msg = f"Timed out. Last output:\n{last_output}" if last_output else "Timed out. No output from claude — check it is installed and authenticated in the container."
    return JSONResponse({"status": "error", "message": msg})


@app.post("/start-worktree")
async def start_worktree_session(req: StartRequest):
    ws = config.get_workspot(req.workspot)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{req.workspot}'"})

    if not await check_claude_auth(ws):
        return JSONResponse({
            "status": "error",
            "message": "Claude is not authenticated. Run 'claude' interactively first.",
        })

    date_str = datetime.utcnow().strftime("%Y%m%d")
    hex_suffix = secrets.token_hex(2)
    branch = f"wt-{date_str}-{hex_suffix}"
    worktree_path = f"/tmp/claude-worktrees/{branch}"
    output_file = f"/tmp/claude-rc-wt-{branch}.txt"

    git_result = await _runtime(ws).run_shell(ws, f"git -C {ws.dir} worktree add -b {branch} {worktree_path} 2>&1")
    if git_result.returncode != 0:
        return JSONResponse({
            "status": "error",
            "message": f"Failed to create worktree: {(git_result.stdout + git_result.stderr).strip()}",
        })

    ok, err_msg = await launch_session(ws, worktree_path, output_file)
    if not ok:
        return JSONResponse({"status": "error", "message": err_msg})

    url, last_output = await poll_for_url(ws, output_file)
    if url:
        history_store.save_session(url, workspot=ws.name, worktree=branch)
        registry.upsert_session(SessionRecord(
            id=secrets.token_urlsafe(8),
            workspot=ws.name,
            server_key=_server_key(ws),
            label=branch,
            runtime=ws.runtime,
            container=ws.container,
            repo_root=ws.dir,
            working_dir=worktree_path,
            branch=branch,
            worktree_path=worktree_path,
            url=url,
            status=SessionStatus.running,
            created_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            source="launcher",
            server_session_name=branch,
        ))
        return JSONResponse({"status": "ok", "url": url, "worktree": branch, "reused": False, "workspot": ws.name})

    msg = f"Timed out. Last output:\n{last_output}" if last_output else "Timed out. No output from claude — check it is installed and authenticated in the container."
    return JSONResponse({"status": "error", "message": msg})
