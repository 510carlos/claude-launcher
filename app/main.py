from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.discovery import discover_all
from app.hook_ingest import ingest_session_hook
from app.models import AddWorkspotRequest, KillRequest, SessionHookPayload, StartRequest, Workspot, WorkspotSource
from app.registry import SessionHistoryStore, SessionRegistry
from app.runtime import RuntimeManager
from app.server_manager import ServerManager
from app.session_manager import SessionManager
from app.workspot_store import WorkspotStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

config = load_config()
registry = SessionRegistry(config.session_registry_file)
history_store = SessionHistoryStore(config.session_history_file, max_sessions=config.max_sessions)
workspot_store = WorkspotStore(config.workspot_config_file)
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

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


async def _reconcile_loop():
    await asyncio.sleep(5)  # initial delay
    while True:
        try:
            updated = await session_manager.reconcile_sessions()
            if updated:
                log.info("Reconciler updated %d sessions", updated)
        except Exception as e:
            log.error("Reconciler error: %s", e)
        await asyncio.sleep(12)


@app.on_event("startup")
async def start_reconciler():
    asyncio.create_task(_reconcile_loop())


@app.get("/")
@app.get("/sessions")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/workspots")
@app.get("/workspots")
async def list_workspots():
    return JSONResponse([
        {
            "name": w.name,
            "runtime": w.runtime.value,
            "container": w.container,
            "dir": w.dir,
            "claude_bin": w.claude_bin,
            "server_capacity": w.server_capacity,
            "source": w.source.value,
        }
        for w in get_all_workspots()
    ])


@app.get("/api/workspots/health")
async def list_workspot_health():
    results = await asyncio.gather(*(server_manager.workspot_health(ws) for ws in get_all_workspots()))
    return JSONResponse(list(results))


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
