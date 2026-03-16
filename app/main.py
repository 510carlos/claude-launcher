from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.models import KillRequest, StartRequest
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
    session = next((item for item in registry.list_sessions() if item.id == session_id), None)
    if not session:
        return JSONResponse({"status": "error", "message": f"Unknown session '{session_id}'"}, status_code=404)
    return JSONResponse(session.model_dump(mode="json"))


@app.get("/status")
async def get_status():
    results = []
    for workspot in config.workspots:
        url = await session_manager.existing_session_url(workspot)
        results.append({"name": workspot.name, "running": url is not None, "url": url})
    return JSONResponse(results)


@app.post("/api/sessions")
@app.post("/start")
async def start_session(req: StartRequest):
    return JSONResponse(await session_manager.create_session(req))


@app.post("/start-worktree")
async def start_worktree_session(req: StartRequest):
    payload = req.model_copy(update={"worktree": True})
    return JSONResponse(await session_manager.create_session(payload))


@app.post("/api/sessions/{session_id}/kill")
async def kill_session_by_id(session_id: str):
    session = next((item for item in registry.list_sessions() if item.id == session_id), None)
    if not session:
        return JSONResponse({"status": "error", "message": f"Unknown session '{session_id}'"}, status_code=404)
    workspot = config.get_workspot(session.workspot)
    if not workspot:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{session.workspot}'"}, status_code=404)
    return JSONResponse(await session_manager.kill_workspot(workspot))


@app.post("/kill")
async def kill_session_endpoint(req: KillRequest):
    ws = config.get_workspot(req.workspot)
    if not ws:
        return JSONResponse({"status": "error", "message": f"Unknown workspot '{req.workspot}'"})
    return JSONResponse(await session_manager.kill_workspot(ws))
