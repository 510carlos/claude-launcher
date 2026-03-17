# Claude Launcher

The missing piece between your development environments and the Claude app on your phone.

Claude Launcher doesn't rebuild Claude's UI. It runs `claude remote-control` inside your devcontainers and workspaces, and hands you the URL. You use the **real Claude app** — on your phone, tablet, or browser — connected directly to your actual dev environment.

```
Phone → Tailscale → Claude Launcher → docker exec / local shell → claude remote-control → URL → Claude app
```

**One tap. Real Claude UI. Your code.**

## How This Is Different

Every other project in this space rebuilds the chat interface — custom web UIs, xterm.js terminal emulators, Electron wrappers, Tauri apps. They put a middleman between you and Claude.

Claude Launcher doesn't do that. It's a **session orchestrator**, not a chat client. It solves one problem: getting a `claude remote-control` URL from the right environment to your phone, fast.

| | Claude Launcher | Other tools |
|---|---|---|
| **Chat UI** | The real Claude app (claude.ai / mobile) | Custom-built web or desktop UI |
| **What it does** | Spawns `claude remote-control`, returns the URL | Wraps the CLI, renders output in its own interface |
| **Phone experience** | Native Claude app with full features | Browser tab with a custom UI |
| **Complexity** | 3 Python deps, vanilla JS, no build step | Next.js, Electron, Tauri, React, xterm.js, etc. |
| **Multi-environment** | Docker containers + host machines from one dashboard | Usually single-machine |

This means you get all of Claude's features — tool use, artifacts, conversation history, mobile notifications — without any re-implementation. When Anthropic ships improvements to the Claude app, you get them immediately.

## Features

- **Multi-workspace dashboard** — Manage devcontainers and local directories from one place
- **Health monitoring** — See which workspaces are healthy, authenticated, and ready
- **Parallel sessions** — Multiple sessions per workspace, or isolated git worktree branches
- **Mobile-first PWA** — Installable on your home screen, designed for phone-sized screens
- **Docker + host runtimes** — Run in containers via `docker exec` or directly on the host
- **Auto-discovery** — Scans Docker containers and local dirs to suggest new workspaces
- **Session lifecycle** — Start, monitor, kill, and clean up sessions
- **Webhook callbacks** — Hook-based URL capture via Claude's SessionStart hook
- **Persistent state** — Survives container restarts
- **Tailscale integration** — Secure access from any device on your tailnet
- **Minimal** — FastAPI + vanilla JS, no build step, 3 Python dependencies

## Prerequisites

- **Docker** + **Docker Compose v2**
- A running devcontainer (or local directory) with the [`claude` CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- A [Tailscale](https://tailscale.com) account (for remote access; optional for local-only use)

## Quick Start

```bash
git clone https://github.com/your-org/claude-launcher.git
cd claude-launcher
cp .env.example .env
```

Edit `.env` with your workspot definitions (see [Configuration](#configuration) below), then:

```bash
docker compose up -d --build
```

The dashboard is now available at:

- **Local**: http://localhost:8765
- **Tailscale**: http://\<tailscale-ip\>:8765

Open it on your phone, tap **Start Session** on a workspace, and you'll get a URL that opens directly in the Claude app.

## Configuration

All configuration is done through environment variables in `.env`.

### Workspots

Workspots are the core concept — each one is a named environment where Claude can run. Define them as a JSON array in the `WORKSPOTS` variable:

```bash
WORKSPOTS='[
  {
    "name": "my-project",
    "container": "devcontainer-app-1",
    "dir": "/workspaces/my-project"
  },
  {
    "name": "local-scripts",
    "container": null,
    "dir": "/home/user/scripts"
  }
]'
```

Each workspot object supports:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier shown in the dashboard |
| `dir` | Yes | Working directory (inside the container or on the host) |
| `container` | No | Docker container name. Set to `null` or omit for host runtime |
| `runtime` | No | `"docker"` or `"host"`. Auto-detected from `container` if omitted |
| `claude_bin` | No | Path to the `claude` binary. Default: `"claude"` |
| `server_capacity` | No | Max concurrent sessions. Default: `32` |
| `env` | No | Extra environment variables as `{"KEY": "value"}` |

**Finding your container name:**

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

**Workspace trust:** The working directory must have workspace trust accepted. Check the container's `~/.claude.json` for `hasTrustDialogAccepted: true`, or run `claude` interactively once to accept it.

### Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPOTS` | `[]` | JSON array of workspot definitions (see above) |
| `PORT` | `8765` | Dashboard port |
| `URL_CAPTURE_TIMEOUT` | `30` | Seconds to wait for `claude remote-control` to output a URL |
| `CLAUDE_GLOBAL_FLAGS` | `""` | Flags passed to `claude` before the subcommand (e.g. `--plugin-dir ...`) |
| `CLAUDE_RC_FLAGS` | `""` | Flags passed to the `remote-control` subcommand (e.g. `--permission-mode bypassPermissions`) |
| `MAX_SESSIONS` | `10` | Number of recent sessions to keep in history |
| `DEFAULT_SERVER_CAPACITY` | `32` | Default max concurrent sessions per workspot |
| `SESSION_REGISTRY_FILE` | `/data/session-registry.json` | Path to session registry |
| `SESSION_HISTORY_FILE` | `/data/sessions.json` | Path to session history |
| `WORKSPOT_CONFIG_FILE` | `/data/workspots.json` | Path to file-backed workspot store |
| `DISCOVERY_SCAN_DIRS` | `~/git/` | Comma-separated directories for auto-discovery |
| `DISCOVERY_DOCKER_ENABLED` | `true` | Enable Docker container auto-discovery |
| `DISCOVERY_LOCAL_ENABLED` | `true` | Enable local directory auto-discovery |
| `TAILSCALE_AUTHKEY` | — | Tailscale auth key for remote access |
| `TAILSCALE_HOSTNAME` | `claude-launcher` | Hostname shown in your Tailscale admin panel |
| `TS_KEY_EXPIRES` | — | Auth key expiry date (ISO format, e.g. `2026-06-05`). Used for expiry warnings |

### Legacy Variables

These are supported for backward compatibility with single-workspot setups:

| Variable | Description |
|----------|-------------|
| `DEVCONTAINER_NAME` | Container name (prefer `WORKSPOTS` instead) |
| `WORKING_DIR` | Working directory inside the container |

## Tailscale Setup

Tailscale provides secure remote access so you can reach the launcher from your phone or any device on your tailnet.

1. Go to [Tailscale Admin → Settings → Keys](https://login.tailscale.com/admin/settings/keys)
2. Generate a **reusable** auth key tagged `tag:claude-launcher`
3. Set `TAILSCALE_AUTHKEY` and `TS_KEY_EXPIRES` in `.env`

**Recommended ACL** (lets your personal devices reach the launcher):

```json
{
  "action": "accept",
  "src": ["autogroup:member"],
  "dst": ["tag:claude-launcher:8765"]
}
```

**Rotating the key:**

```bash
# Update TAILSCALE_AUTHKEY and TS_KEY_EXPIRES in .env, then:
docker compose down && docker compose up -d
```

> Always bring the full stack down before recreating. Using `--force-recreate` on only the tailscale service breaks `network_mode: service:claude-launcher`.

## Usage

### Starting a Session

1. Open the dashboard on your phone
2. On the **Workspaces** page, find your workspace (green = healthy)
3. Tap **Start Session** — optionally add a label or branch name
4. Wait a few seconds for the URL to appear
5. Tap the URL — it opens in the Claude app, connected to your workspace

From there you're in the real Claude interface with full access to your codebase.

### Worktree Sessions

Tap **New Worktree Session** to create an isolated git worktree under `/tmp/claude-worktrees/` with an auto-generated branch name (`wt-YYYYMMDD-xxxx`). This lets you run parallel Claude sessions on separate branches without conflicts.

### Managing Sessions

Switch to the **Sessions** page to see all sessions grouped by status (Running / Pending / Stopped). From here you can:

- **Kill** a running session to stop the `claude remote-control` process
- **Delete** stopped sessions to clean up history

### Auto-Discovery

The launcher can scan your environment for potential workspaces that aren't configured yet. It checks Docker containers and local directories for:

- Claude CLI availability
- Git repositories
- Authentication status

Results are available via `GET /api/discover` and categorized as compatible, partial, or incompatible.

## API Reference

All endpoints return JSON.

### Workspots

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/workspots` | List all configured workspots |
| `GET` | `/api/workspots/health` | Health report for each workspot |
| `POST` | `/api/workspots` | Add a new workspot (file-backed) |
| `DELETE` | `/api/workspots/{name}` | Remove a file-backed workspot |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/sessions` | List all sessions (optional `?workspot=name` filter) |
| `GET` | `/api/sessions/{id}` | Get a single session |
| `POST` | `/api/sessions` | Start a new session |
| `POST` | `/api/sessions/{id}/kill` | Kill a running session |
| `DELETE` | `/api/sessions/{id}` | Delete a session record |
| `GET` | `/api/sessions/live.json` | List only pending/running sessions |

### Servers

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/servers` | List server records |
| `POST` | `/api/servers/{workspot}/ensure` | Start or reconcile a workspot's server |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/status` | Quick status summary per workspot |
| `POST` | `/api/hooks/session-start` | Webhook for session URL callbacks |
| `GET` | `/api/discover` | Auto-discover potential workspaces |
| `POST` | `/kill` | Kill all sessions for a workspot |
| `POST` | `/start-worktree` | Start a worktree session |

### Starting a Session via API

```bash
curl -X POST http://localhost:8765/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"workspot": "my-project"}'
```

Optional fields: `label` (string), `branch` (string), `worktree` (boolean).

## Architecture

```
┌─────────────────────┐          ┌──────────────────────┐
│  Your Phone          │          │  Claude app           │
│  (Claude Launcher    │          │  (claude.ai / mobile) │
│   dashboard PWA)     │          │                      │
└─────────┬───────────┘          └──────────▲───────────┘
          │ tap "Start Session"             │ tap the URL
          │                                 │
          │ Tailscale VPN                   │
┌─────────▼─────────────────────────────────┼───────────┐
│  Claude Launcher (FastAPI)                │           │
│                                           │           │
│  ┌──────────────┐  ┌──────────────┐       │           │
│  │ SessionMgr   │  │ ServerMgr    │       │           │
│  │ (lifecycle)  │  │ (health/PID) │       │           │
│  └──────┬───────┘  └──────┬───────┘       │           │
│         │                 │               │           │
│  ┌──────▼─────────────────▼───────┐       │           │
│  │  RuntimeManager                │       │           │
│  │  ┌─────────────┐ ┌──────────┐ │       │           │
│  │  │DockerAdapter│ │HostAdapt.│ │       │           │
│  │  └──────┬──────┘ └────┬─────┘ │       │           │
│  └─────────┼─────────────┼───────┘       │           │
│            │             │               │           │
│  ┌─────────▼──┐  ┌──────▼────────┐      │           │
│  │docker exec │  │ local shell   │      │           │
│  │claude      │  │claude         │      │           │
│  │remote-ctrl │  │remote-ctrl    │──────┘           │
│  └────────────┘  └───────────────┘  returns URL     │
│                                                      │
│  Persistence: /data/*.json (Docker volume)           │
└──────────────────────────────────────────────────────┘
```

The launcher **never touches your conversations**. It only starts the `remote-control` process and captures the URL. All chat traffic flows directly between the Claude app and your environment.

### Key Modules

| Module | Role |
|--------|------|
| `main.py` | FastAPI routes, app initialization |
| `config.py` | Loads and validates `.env` configuration |
| `models.py` | Pydantic models for workspots, sessions, servers |
| `runtime.py` | Docker and host runtime adapters |
| `session_manager.py` | Session creation, polling, and cleanup |
| `server_manager.py` | Server health checks, process tracking |
| `registry.py` | JSON-based persistence for sessions and servers |
| `discovery.py` | Auto-discovery of containers and local repos |
| `workspot_store.py` | File-backed workspot CRUD |
| `hook_ingest.py` | Webhook handler for session callbacks |

## Logs and Troubleshooting

### Viewing Logs

```bash
docker compose logs -f                    # All services
docker compose logs -f claude-launcher    # Launcher only
```

### Common Issues

**"No workspots configured"**
Check that `WORKSPOTS` is valid JSON in your `.env`. Use `docker compose logs` to see parse errors.

**Session stays "pending"**
- The `claude` CLI may not be installed or not in `$PATH` inside the container. Set `claude_bin` to the full path (e.g. `/home/node/.local/bin/claude`).
- Workspace trust may not be accepted. Run `claude` interactively once in the working directory.
- Check `URL_CAPTURE_TIMEOUT` — increase it if your environment is slow to start.

**Health check shows "auth missing"**
Run `claude` interactively inside the container/host to complete authentication. The launcher checks for `~/.claude/.credentials.json`.

**Tailscale not connecting**
- Verify `TAILSCALE_AUTHKEY` is a valid, non-expired reusable key
- Check that the `tag:claude-launcher` tag exists in your Tailscale ACLs
- Always `docker compose down` then `docker compose up -d` (not `--force-recreate`)

**Container not found**
Run `docker ps --format 'table {{.Names}}\t{{.Status}}'` to verify the container name matches your workspot config.

### Stopping

```bash
docker compose down          # Stop services
docker compose down -v       # Stop and remove volumes (clears all state)
```

## Development

To run the launcher locally without Docker:

```bash
cd app
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload
```

The frontend is plain HTML/JS in `app/static/` — edit and reload, no build step needed.

## License

MIT
