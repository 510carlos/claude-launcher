from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.db import Database
from app.discovery import discover_all
from app.hook_ingest import ingest_session_hook
from app.models import AddWorkspotRequest, KillRequest, ResumeRequest, SessionHookPayload, StartRequest, Workspot, WorkspotSource
from app.registry import SessionHistoryStore, SessionRegistry
from app.runtime import RuntimeManager
from app.server_manager import ServerManager
from app.session_manager import SessionManager
from app.workspot_store import WorkspotStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

config = load_config()
db = Database(config.db_file)
db.migrate_from_json(
    registry_json=config.session_registry_file,
    history_json=config.session_history_file,
    workspots_json=config.workspot_config_file,
)
registry = SessionRegistry(db)
history_store = SessionHistoryStore(db, max_sessions=config.max_sessions)
workspot_store = WorkspotStore(db)
runtime_manager = RuntimeManager(local_env=config.local_claude_env)
server_manager = ServerManager(registry=registry, runtime_manager=runtime_manager)
session_manager = SessionManager(
    config=config,
    registry=registry,
    history_store=history_store,
    runtime_manager=runtime_manager,
    server_manager=server_manager,
    workspot_resolver=lambda name: find_workspot(name),
)


def get_all_workspots() -> list[Workspot]:
    return workspot_store.merge_with_env(config.workspots)


def find_workspot(name: str) -> Workspot | None:
    return next((ws for ws in get_all_workspots() if ws.name == name), None)

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
BUILD_DIR = APP_DIR / "frontend" / "dist"

app = FastAPI()

_use_build = BUILD_DIR.exists() and (BUILD_DIR / "index.html").exists()

# Serve built frontend assets if available, otherwise legacy static
if _use_build:
    log.info("Serving built frontend from %s", BUILD_DIR)
    if (BUILD_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=BUILD_DIR / "assets"), name="assets")
else:
    log.info("No built frontend found, serving legacy static files")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


async def _reconcile_loop():
    await asyncio.sleep(5)  # initial delay
    while True:
        try:
            updated = await session_manager.reconcile_sessions()
            if updated:
                log.info("Reconciler updated %d sessions", updated)
            purged = registry.delete_stale_sessions()
            if purged:
                log.info("Purged %d stale sessions older than 24h", purged)
        except Exception as e:
            log.error("Reconciler error: %s", e)
        await asyncio.sleep(12)


@app.on_event("startup")
async def start_reconciler():
    asyncio.create_task(_reconcile_loop())


@app.on_event("startup")
async def ensure_home_workspot():
    """Ensure ~/ exists as a workspot and is trusted, so there's always a root environment to launch from."""
    import os
    home = os.path.expanduser("~")
    home_ws = Workspot(name="home", dir=home, runtime="host")
    # Add to workspot store if not already present
    try:
        workspot_store.add(home_ws)
        log.info("Added default 'home' workspot at %s", home)
    except ValueError:
        pass  # already exists
    # Trust it
    await session_manager.ensure_workspace_trusted(home_ws, home)


def _resolve_static(filename: str) -> Path:
    """Resolve a static file from build dir or legacy static dir."""
    if _use_build and (BUILD_DIR / filename).exists():
        return BUILD_DIR / filename
    return STATIC_DIR / filename


@app.get("/api/config")
async def get_config():
    return JSONResponse({"app_name": config.app_name})


@app.get("/")
@app.get("/sessions")
async def index():
    return FileResponse(_resolve_static("index.html"))


@app.get("/manifest.json")
async def manifest():
    name = config.app_name
    short = f"{name} - CL" if name != "Claude Launcher" else "Claude"
    return JSONResponse({
        "name": f"{name} - Claude Launcher",
        "short_name": short,
        "description": "Start Claude Code sessions in your dev environment",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0b1220",
        "theme_color": "#0b1220",
        "orientation": "portrait",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }, headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
async def service_worker():
    return FileResponse(_resolve_static("sw.js"), media_type="application/javascript")


@app.get("/icon-192.png")
async def icon_192():
    return FileResponse(_resolve_static("icon-192.png"), media_type="image/png")


@app.get("/icon-512.png")
async def icon_512():
    return FileResponse(_resolve_static("icon-512.png"), media_type="image/png")


@app.get("/api/workspots")
@app.get("/workspots")
async def list_workspots():
    import os
    home = os.path.expanduser("~")
    all_ws = get_all_workspots()
    # Ensure home is always last
    non_home = [w for w in all_ws if w.dir != home]
    home_ws = [w for w in all_ws if w.dir == home]
    ordered = non_home + home_ws
    return JSONResponse([
        {
            "name": w.name,
            "runtime": w.runtime.value,
            "container": w.container,
            "dir": w.dir,
            "claude_bin": w.claude_bin,
            "server_capacity": w.server_capacity,
            "source": "env" if w.dir == home else w.source.value,
        }
        for w in ordered
    ])


@app.get("/api/workspots/health")
async def list_workspot_health():
    results = await asyncio.gather(*(server_manager.workspot_health(ws) for ws in get_all_workspots()))
    return JSONResponse(list(results))


@app.post("/api/workspots/{name}/recheck")
async def recheck_workspot(name: str):
    """Re-run health for a single workspot."""
    ws = find_workspot(name)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{name}'"}, status_code=404)
    health = await server_manager.workspot_health(ws)
    return JSONResponse(health)


@app.post("/api/workspots/{name}/fix")
async def fix_workspot(name: str):
    """Auto-fix common issues: restart stopped containers, trust workspace."""
    ws = find_workspot(name)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{name}'"}, status_code=404)

    fixes_applied: list[str] = []

    # Fix: restart stopped Docker container
    if ws.container:
        import asyncio as _aio
        proc = await _aio.create_subprocess_exec(
            "docker", "start", ws.container,
            stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            fixes_applied.append(f"Started container {ws.container}")
            # Give it a moment to fully start
            await _aio.sleep(3)

    runtime = runtime_manager.for_workspot(ws)

    # Fix: auto-trust workspace directory
    await session_manager.ensure_workspace_trusted(ws, ws.dir)
    fixes_applied.append("Workspace trusted")

    # Re-run health after fixes
    health = await server_manager.workspot_health(ws)
    return JSONResponse({
        "status": "ok",
        "fixes": fixes_applied,
        "health": health,
    })


@app.get("/api/servers")
async def list_servers():
    for workspot in get_all_workspots():
        await server_manager.reconcile_server(workspot)
    return JSONResponse([record.model_dump(mode="json") for record in registry.list_servers()])


@app.post("/api/servers/{workspot}/ensure")
async def ensure_server(workspot: str):
    ws = find_workspot(workspot)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{workspot}'"}, status_code=404)
    record = await server_manager.ensure_server(ws)
    return JSONResponse({"status": "ok", "server": record.model_dump(mode="json")})


@app.get("/api/sessions")
@app.get("/sessions")
async def get_sessions(workspot: str | None = None):
    sessions = registry.list_sessions(workspot=workspot)
    return JSONResponse([session.model_dump(mode="json") for session in sessions])


@app.get("/api/sessions/live.json")
async def get_live_sessions():
    live = [
        session.model_dump(mode="json")
        for session in registry.list_sessions()
        if session.status.value in {"pending", "running"}
    ]
    return JSONResponse({"sessions": live})


@app.get("/api/sessions/{session_id}/output")
async def get_session_output(session_id: str, tail: int = 50):
    result = await session_manager.get_session_output(session_id, tail=tail)
    status_code = 200 if result.get("status") == "ok" else 404
    return JSONResponse(result, status_code=status_code)


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    session = registry.get_session(session_id)
    if not session:
        return JSONResponse({"status": "error", "message": f"Unknown session '{session_id}'"}, status_code=404)
    return JSONResponse(session.model_dump(mode="json"))


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    deleted = registry.delete_session(session_id)
    if not deleted:
        return JSONResponse({"status": "error", "message": f"Unknown session '{session_id}'"}, status_code=404)
    return JSONResponse({"status": "ok", "session_id": session_id})


@app.delete("/api/sessions")
async def delete_ended_sessions():
    count = registry.delete_ended_sessions()
    return JSONResponse({"status": "ok", "deleted": count})


@app.get("/status")
async def get_status():
    results = []
    for workspot in get_all_workspots():
        sessions = registry.list_sessions(workspot=workspot.name)
        live = [s for s in sessions if s.status.value in {"pending", "running"}]
        results.append({
            "name": workspot.name,
            "running": bool(live),
            "count": len(live),
            "url": next((s.url for s in live if s.url), None),
        })
    return JSONResponse(results)


@app.get("/api/workspots/{name}/conversations")
async def list_conversations(name: str, limit: int = 20):
    ws = find_workspot(name)
    if not ws:
        return JSONResponse(
            {"status": "error", "message": f"Unknown workspot '{name}'"},
            status_code=404,
        )
    from app.conversation_scanner import list_conversations as scan
    conversations = scan(ws.dir, limit=limit)
    return JSONResponse([c.model_dump(mode="json") for c in conversations])


@app.post("/api/sessions/resume")
async def resume_session_endpoint(req: ResumeRequest):
    return JSONResponse(await session_manager.resume_session(req))


@app.post("/api/sessions")
@app.post("/start")
async def start_session(req: StartRequest):
    return JSONResponse(await session_manager.create_session(req))


@app.post("/start-worktree")
async def start_worktree_session(req: StartRequest):
    """Legacy endpoint — now just sets worktree=True and delegates."""
    payload = req.model_copy(update={"worktree": True})
    return JSONResponse(await session_manager.create_session(payload))


@app.post("/api/hooks/session-start")
async def session_start_hook(payload: SessionHookPayload):
    result = ingest_session_hook(registry=registry, history_store=history_store, payload=payload)
    status_code = 200 if result.get("status") == "ok" else 404
    return JSONResponse(result, status_code=status_code)


@app.post("/api/sessions/{session_id}/kill")
async def kill_session_by_id(session_id: str):
    result = await session_manager.kill_session(session_id)
    status_code = 200 if result.get("status") == "ok" else 404
    return JSONResponse(result, status_code=status_code)


@app.post("/kill")
async def kill_session_endpoint(req: KillRequest):
    ws = find_workspot(req.workspot)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{req.workspot}'"})
    return JSONResponse(await session_manager.kill_workspot(ws))


@app.get("/api/discover")
async def discover_environments():
    result = await discover_all(
        scan_dirs=config.discovery_scan_dirs,
        existing_workspots=get_all_workspots(),
        docker_enabled=config.discovery_docker_enabled,
        local_enabled=config.discovery_local_enabled,
    )
    return JSONResponse(result)


@app.post("/api/workspots")
async def add_workspot(req: AddWorkspotRequest):
    all_ws = get_all_workspots()
    if any(ws.name == req.name for ws in all_ws):
        return JSONResponse(
            {"status": "error", "message": f"Workspot '{req.name}' already exists"},
            status_code=409,
        )
    workspot = Workspot(
        name=req.name,
        runtime=req.runtime,
        dir=req.dir,
        container=req.container,
        claude_bin=req.claude_bin,
        server_capacity=req.server_capacity,
        env=req.env,
        source=WorkspotSource.file,
    )
    workspot_store.add(workspot)
    return JSONResponse({"status": "ok", "workspot": workspot.model_dump(mode="json")})


@app.get("/api/updates/check")
async def check_updates():
    """Check if the app is behind origin/main."""
    import subprocess
    repo = APP_DIR.parent
    try:
        subprocess.run(["git", "-C", str(repo), "fetch", "origin", "main", "--quiet"], timeout=15, capture_output=True)
        result = subprocess.run(
            ["git", "-C", str(repo), "log", "HEAD..origin/main", "--oneline"],
            capture_output=True, text=True, timeout=10,
        )
        commits = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        current = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%h %s"],
            capture_output=True, text=True, timeout=5,
        )
        return JSONResponse({
            "status": "ok",
            "behind": len(commits),
            "commits": commits[:20],
            "current": current.stdout.strip(),
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})


@app.post("/api/updates/apply")
async def apply_update():
    """Pull latest from origin/main, rebuild frontend, restart service."""
    import subprocess
    repo = APP_DIR.parent
    steps: list[dict] = []
    try:
        # Reset to origin/main (handles dirty working tree and diverged history)
        subprocess.run(
            ["git", "-C", str(repo), "fetch", "origin", "main", "--quiet"],
            capture_output=True, text=True, timeout=15,
        )
        r = subprocess.run(
            ["git", "-C", str(repo), "reset", "--hard", "origin/main"],
            capture_output=True, text=True, timeout=15,
        )
        steps.append({"step": "git reset", "ok": r.returncode == 0, "output": r.stdout.strip() or r.stderr.strip()})
        if r.returncode != 0:
            return JSONResponse({"status": "error", "message": f"Git reset failed: {r.stderr.strip()}", "steps": steps})

        # Rebuild frontend
        frontend_dir = APP_DIR / "frontend"
        r = subprocess.run(
            ["bun", "run", "build"],
            cwd=str(frontend_dir), capture_output=True, text=True, timeout=60,
        )
        steps.append({"step": "bun run build", "ok": r.returncode == 0, "output": r.stdout.strip() or r.stderr.strip()})
        if r.returncode != 0:
            return JSONResponse({"status": "error", "message": "Frontend build failed", "steps": steps})

        # Schedule restart after response is sent
        async def _restart():
            await asyncio.sleep(1)
            subprocess.run(["systemctl", "--user", "restart", "claude-launcher"], timeout=10)

        asyncio.create_task(_restart())
        steps.append({"step": "restart", "ok": True, "output": "Scheduled"})
        return JSONResponse({"status": "ok", "steps": steps, "message": "Update applied. Restarting..."})

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e), "steps": steps})


@app.delete("/api/workspots/{name}")
async def remove_workspot(name: str):
    # Refuse to delete env-defined workspots
    if any(ws.name == name for ws in config.workspots):
        return JSONResponse(
            {"status": "error", "message": f"Workspot '{name}' is defined in environment and cannot be removed from the UI"},
            status_code=409,
        )
    if not workspot_store.remove(name):
        return JSONResponse(
            {"status": "error", "message": f"Workspot '{name}' not found"},
            status_code=404,
        )
    return JSONResponse({"status": "ok", "name": name})
