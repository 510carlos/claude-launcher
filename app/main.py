import asyncio
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

CLAUDE_GLOBAL_FLAGS = os.getenv("CLAUDE_GLOBAL_FLAGS", "")
CLAUDE_RC_FLAGS = os.getenv("CLAUDE_RC_FLAGS", "")
TS_KEY_EXPIRES = os.getenv("TS_KEY_EXPIRES", "")
URL_CAPTURE_TIMEOUT = int(os.getenv("URL_CAPTURE_TIMEOUT", "30"))
SESSION_HISTORY_FILE = Path("/data/sessions.json")
MAX_SESSIONS = 10

# Local env for the claude-bot workspot (native subprocess)
LOCAL_CLAUDE_ENV = {
    **os.environ,
    "HOME": "/home/claude-config",
    "XDG_DATA_HOME": "/home/claude-share",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def parse_workspots() -> list[dict]:
    raw = os.getenv("WORKSPOTS", "[]")
    try:
        return json.loads(raw)
    except Exception:
        log.error("Failed to parse WORKSPOTS env var")
        return []


WORKSPOTS = parse_workspots()


def get_workspot(name: str) -> dict | None:
    return next((w for w in WORKSPOTS if w["name"] == name), None)


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def check_ts_key_expiry():
    if not TS_KEY_EXPIRES:
        return
    try:
        expiry = datetime.fromisoformat(TS_KEY_EXPIRES).replace(tzinfo=timezone.utc)
        days_left = (expiry - datetime.now(timezone.utc)).days
        if days_left <= 14:
            log.warning(
                "Tailscale auth key expires in %d day(s) (%s). Rotate soon!",
                days_left,
                TS_KEY_EXPIRES,
            )
    except ValueError:
        log.warning("TS_KEY_EXPIRES '%s' is not a valid ISO date, skipping check.", TS_KEY_EXPIRES)


# ---------------------------------------------------------------------------
# Session history
# ---------------------------------------------------------------------------

def load_sessions() -> list:
    if SESSION_HISTORY_FILE.exists():
        try:
            return json.loads(SESSION_HISTORY_FILE.read_text())
        except Exception:
            return []
    return []


def save_session(url: str, workspot: str, worktree: str | None = None):
    SESSION_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    sessions = load_sessions()
    sessions.insert(0, {
        "url": url,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "workspot": workspot,
        "worktree": worktree,
    })
    sessions = sessions[:MAX_SESSIONS]
    SESSION_HISTORY_FILE.write_text(json.dumps(sessions, indent=2))


# ---------------------------------------------------------------------------
# Execution helpers
# ---------------------------------------------------------------------------

async def run_docker_exec(container: str, args: list[str]) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "docker", "exec", container, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()


async def run_local(args: list[str]) -> tuple[int, str, str]:
    """Run a command directly inside the launcher container."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=LOCAL_CLAUDE_ENV,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()


async def check_claude_auth(workspot: dict) -> bool:
    container = workspot.get("container")
    creds = "/home/node/.claude/.credentials.json"
    if container:
        rc, out, _ = await run_docker_exec(container, ["bash", "-c",
            f"test -s {creds} && echo ok"])
    else:
        local_creds = "/home/claude-config/.claude/.credentials.json"
        rc, out, _ = await run_local(["bash", "-c",
            f"test -s {local_creds} && echo ok"])
    return rc == 0 and "ok" in out


async def is_session_running(workspot: dict) -> str | None:
    """Return existing URL if a claude remote-control process is running for this workspot."""
    container = workspot.get("container")
    output_file = _output_file(workspot["name"])

    if container:
        rc, _, _ = await run_docker_exec(container, ["pgrep", "-f", "claude remote-control"])
        if rc != 0:
            return None
        rc2, out2, _ = await run_docker_exec(container, ["cat", output_file])
    else:
        rc, _, _ = await run_local(["pgrep", "-f", "claude remote-control"])
        if rc != 0:
            return None
        rc2, out2, _ = await run_local(["cat", output_file])

    if rc2 == 0:
        match = re.search(r"https://claude\.ai/code\S+", out2)
        if match:
            return match.group(0)
    # Process running but no URL in output file — stale process, kill it
    await kill_session(workspot)
    return None


async def kill_session(workspot: dict):
    """Kill any running claude remote-control processes for this workspot."""
    container = workspot.get("container")
    kill_cmd = ["bash", "-c", "pgrep -f 'claude remote-control' | xargs -r kill"]
    if container:
        await run_docker_exec(container, kill_cmd)
    else:
        await run_local(kill_cmd)


def _output_file(workspot_name: str) -> str:
    return f"/tmp/claude-rc-{workspot_name}.txt"


async def poll_for_url(workspot: dict, output_file: str) -> tuple[str | None, str]:
    """Returns (url, last_output). url is None on timeout."""
    container = workspot.get("container")
    deadline = time.monotonic() + URL_CAPTURE_TIMEOUT
    last_output = ""
    while time.monotonic() < deadline:
        await asyncio.sleep(0.5)
        if container:
            rc, out, _ = await run_docker_exec(container, ["cat", output_file])
        else:
            rc, out, _ = await run_local(["cat", output_file])
        if rc == 0:
            last_output = out.strip()
            match = re.search(r"https://claude\.ai/code\S+", out)
            if match:
                return match.group(0), last_output
    return None, last_output


async def launch_session(workspot: dict, working_dir: str, output_file: str) -> tuple[bool, str]:
    """Start claude remote-control detached. Returns (success, error_message)."""
    container = workspot.get("container")
    cmd = f"claude remote-control {CLAUDE_RC_FLAGS}".strip()
    launch = f"cd {working_dir} && {cmd} 2>&1 | tee {output_file}"

    if container:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-d", container, "bash", "-c", launch,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        local_launch = f"{cmd} 2>&1 | tee {output_file}"
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", local_launch,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=LOCAL_CLAUDE_ENV,
            cwd=working_dir,
            start_new_session=True,
        )

    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode().strip()
        if container and "No such container" in err:
            return False, f"Container '{container}' not found."
        return False, err or "Failed to start claude"
    return True, ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    workspot: str
    worktree: Optional[bool] = False


class KillRequest(BaseModel):
    workspot: str


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/workspots")
async def list_workspots():
    return JSONResponse([{"name": w["name"]} for w in WORKSPOTS])


@app.get("/sessions")
async def get_sessions():
    return JSONResponse(load_sessions())


@app.get("/status")
async def get_status():
    """Return running state for all workspots."""
    results = await asyncio.gather(*[
        is_session_running(ws) for ws in WORKSPOTS
    ])
    return JSONResponse([
        {"name": ws["name"], "running": url is not None, "url": url}
        for ws, url in zip(WORKSPOTS, results)
    ])


@app.post("/kill")
async def kill_session_endpoint(req: KillRequest):
    ws = get_workspot(req.workspot)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{req.workspot}'"})
    await kill_session(ws)
    output_file = _output_file(ws["name"])
    container = ws.get("container")
    if container:
        await run_docker_exec(container, ["bash", "-c", f"rm -f {output_file}"])
    else:
        await run_local(["bash", "-c", f"rm -f {output_file}"])
    return JSONResponse({"status": "ok"})


@app.post("/start")
async def start_session(req: StartRequest):
    ws = get_workspot(req.workspot)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{req.workspot}'"})

    existing_url = await is_session_running(ws)
    if existing_url:
        return JSONResponse({"status": "ok", "url": existing_url, "reused": True, "workspot": ws["name"]})

    if not await check_claude_auth(ws):
        return JSONResponse({
            "status": "error",
            "message": "Claude is not authenticated. Run 'claude' interactively first.",
        })

    output_file = _output_file(ws["name"])
    container = ws.get("container")

    # Clear old output file
    if container:
        await run_docker_exec(container, ["bash", "-c", f"rm -f {output_file}"])
    else:
        await run_local(["bash", "-c", f"rm -f {output_file}"])

    ok, err = await launch_session(ws, ws["dir"], output_file)
    if not ok:
        return JSONResponse({"status": "error", "message": err})

    url, last_output = await poll_for_url(ws, output_file)
    if url:
        save_session(url, workspot=ws["name"])
        return JSONResponse({"status": "ok", "url": url, "reused": False, "workspot": ws["name"]})

    msg = f"Timed out. Last output:\n{last_output}" if last_output else "Timed out. No output from claude — check it is installed and authenticated in the container."
    return JSONResponse({"status": "error", "message": msg})


@app.post("/start-worktree")
async def start_worktree_session(req: StartRequest):
    ws = get_workspot(req.workspot)
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

    container = ws.get("container")
    git_cmd = f"git -C {ws['dir']} worktree add -b {branch} {worktree_path} 2>&1"

    if container:
        rc, out, err = await run_docker_exec(container, ["bash", "-c", git_cmd])
    else:
        rc, out, err = await run_local(["bash", "-c", git_cmd])

    if rc != 0:
        return JSONResponse({
            "status": "error",
            "message": f"Failed to create worktree: {(out + err).strip()}",
        })

    ok, err_msg = await launch_session(ws, worktree_path, output_file)
    if not ok:
        return JSONResponse({"status": "error", "message": err_msg})

    url, last_output = await poll_for_url(ws, output_file)
    if url:
        save_session(url, workspot=ws["name"], worktree=branch)
        return JSONResponse({"status": "ok", "url": url, "worktree": branch, "reused": False, "workspot": ws["name"]})

    msg = f"Timed out. Last output:\n{last_output}" if last_output else "Timed out. No output from claude — check it is installed and authenticated in the container."
    return JSONResponse({"status": "error", "message": msg})
