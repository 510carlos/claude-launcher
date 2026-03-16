from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.hook_ingest import ingest_session_hook
from app.models import KillRequest, SessionHookPayload, StartRequest
from app.registry import SessionHistoryStore, SessionRegistry
from app.runtime import RuntimeManager
from app.server_manager import ServerManager
from app.session_manager import SessionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

config = load_config()
registry = SessionRegistry(config.session_registry_file)
history_store = SessionHistoryStore(config.session_history_file, max_sessions=config.max_sessions)
runtime_manager = RuntimeManager(local_env=config.local_claude_env)
server_manager = ServerManager(registry=registry, runtime_manager=runtime_manager)
session_manager = SessionManager(
    config=config,
    registry=registry,
    history_store=history_store,
    runtime_manager=runtime_manager,
    server_manager=server_manager,
)

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
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
        }
        for w in config.workspots
    ])


@app.get("/api/workspots/health")
async def list_workspot_health():
    return JSONResponse([await server_manager.workspot_health(workspot) for workspot in config.workspots])


@app.get("/api/servers")
async def list_servers():
    for workspot in config.workspots:
        await server_manager.reconcile_server(workspot)
    return JSONResponse([record.model_dump(mode="json") for record in registry.list_servers()])


@app.post("/api/servers/{workspot}/ensure")
async def ensure_server(workspot: str):
    ws = config.get_workspot(workspot)
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


@app.get("/status")
async def get_status():
    results = []
    for workspot in config.workspots:
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
    ws = config.get_workspot(req.workspot)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{req.workspot}'"})
    return JSONResponse(await session_manager.kill_workspot(ws))
