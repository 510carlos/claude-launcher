# Claude Launcher

**Start Claude Code sessions on your dev machines from your phone. One tap. Any workspace. No laptop required.**

When you're at your computer, Claude Code is easy — terminal, files, everything right there. But when you're away from your desk — on the couch, commuting, at lunch — you're locked out. You can't SSH into your dev machine from your phone. You can't run `claude remote-control`. You can't pick which repo or branch to work in.

Claude Launcher fixes that. It's a lightweight dashboard that runs on your dev machine, reachable via Tailscale from your phone. Tap a workspace, get a URL, open it in the Claude app. You're coding in your actual dev environment from your phone in seconds.

```
Phone → Tailscale → Claude Launcher → docker exec / local shell → claude remote-control → URL → Claude app
```

**No custom chat UI. No terminal emulators. Just the real Claude app, connected to your real code.**

## How This Is Different

Every other project in this space rebuilds the chat interface — custom web UIs, xterm.js terminal emulators, Electron wrappers, Tauri apps. They put a middleman between you and Claude.

Claude Launcher doesn't do that. It's a **session orchestrator**, not a chat client. It solves one problem: getting you from your phone to your dev environment through Claude, fast.

| | Claude Launcher | Other tools |
|---|---|---|
| **Chat UI** | The real Claude app (claude.ai / mobile) | Custom-built web or desktop UI |
| **What it does** | Spawns `claude remote-control`, returns the URL | Wraps the CLI, renders output in its own interface |
| **Phone experience** | Native Claude app with full features | Browser tab with a custom UI |
| **Multi-environment** | Docker containers + host machines from one dashboard | Usually single-machine |

This means you get all of Claude's features — tool use, artifacts, conversation history, mobile notifications — without any re-implementation. When Anthropic ships improvements to the Claude app, you get them immediately.

## Features

- **One-tap launch** — Tap a workspace, get a Claude session. Random labels auto-generated so you don't have to type on your phone
- **Multi-workspace dashboard** — Manage devcontainers and local directories from one place
- **Health monitoring** — See which workspaces are healthy, authenticated, and ready. Fix issues with one tap
- **Worktree isolation** — Toggle "Use worktree" for isolated branches via Claude's native `--spawn worktree`
- **Auto-discovery** — Scans Docker containers and local repos to find compatible workspaces
- **Session lifecycle** — Start, monitor output, stop, and clean up sessions
- **Background reconciler** — Automatically detects when sessions start, get URLs, or die
- **Real process kill** — SIGTERM for graceful cleanup, SIGKILL as fallback. Claude deregisters from mobile app on clean shutdown
- **Mobile-first PWA** — Installable on your home screen, optimistic updates, relative timestamps
- **Docker + host runtimes** — Run in containers via `docker exec` or directly on the host
- **Tailscale integration** — Secure access from any device on your tailnet
- **Preact frontend** — TypeScript, Signals, Vite build. Legacy vanilla JS fallback included

## Prerequisites

- The [`claude` CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated in your target environments
- A [Tailscale](https://tailscale.com) account (for remote access; optional for local-only use)
- **For container workspaces:** Docker with running devcontainers
- **For host workspaces:** Python 3.10+ with `pip install fastapi uvicorn python-dotenv`

## Quick Start

### Option A: Native (WSL / Linux / macOS)

```bash
git clone https://github.com/510carlos/claude-launcher.git
cd claude-launcher
pip install fastapi uvicorn python-dotenv
cp .env.example .env   # edit with your workspots, or leave empty and use Discovery
```

Start the server:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8765
```

### Option B: Docker Compose

```bash
git clone https://github.com/510carlos/claude-launcher.git
cd claude-launcher
cp .env.example .env   # edit with your workspots
docker compose up -d --build
```

The dashboard is now available at:

- **Local**: http://localhost:8765
- **Tailscale**: http://\<tailscale-ip\>:8765

Open it on your phone, tap **Launch** on a workspace, and you'll get a URL that opens directly in the Claude app.

## Configuration

All configuration is done through environment variables in `.env`.

### Workspots

Workspots are the core concept — each one is a named environment where Claude can run. Define them as a JSON array in the `WORKSPOTS` variable:

```bash
WORKSPOTS='[
  {
    "name": "my-project",
    "container": "devcontainer-app-1",
    "dir": "/workspaces/my-project",
    "claude_bin": "/home/node/.npm-global/bin/claude",
    "env": {"HOME": "/home/node"}
  },
  {
    "name": "local-repo",
    "container": null,
    "dir": "/home/user/git/my-repo",
    "runtime": "host"
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

Or skip manual config entirely — set `WORKSPOTS=[]` and use the **Discover** feature to scan and add workspaces from the UI.

### Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPOTS` | `[]` | JSON array of workspot definitions (see above) |
| `PORT` | `8765` | Dashboard port |
| `URL_CAPTURE_TIMEOUT` | `30` | Seconds to wait for `claude remote-control` to output a URL |
| `CLAUDE_GLOBAL_FLAGS` | `""` | Flags passed before the subcommand |
| `CLAUDE_RC_FLAGS` | `""` | Flags passed to `remote-control` (e.g. `--permission-mode bypassPermissions`) |
| `MAX_SESSIONS` | `10` | Number of recent sessions to keep in history |
| `DEFAULT_SERVER_CAPACITY` | `32` | Default max concurrent sessions per workspot |
| `DEFAULT_CLAUDE_BIN` | `claude` | Default Claude binary path for new workspots |
| `SESSION_REGISTRY_FILE` | `/data/session-registry.json` | Path to session registry |
| `SESSION_HISTORY_FILE` | `/data/sessions.json` | Path to session history |
| `WORKSPOT_CONFIG_FILE` | `/data/workspots.json` | Path to file-backed workspot store |
| `DISCOVERY_SCAN_DIRS` | `~/git/` | Comma-separated directories for auto-discovery |
| `DISCOVERY_DOCKER_ENABLED` | `true` | Enable Docker container scanning |
| `DISCOVERY_LOCAL_ENABLED` | `true` | Enable local directory scanning |
| `TAILSCALE_AUTHKEY` | — | Tailscale auth key for remote access |
| `TAILSCALE_HOSTNAME` | `claude-launcher` | Hostname shown in your Tailscale admin panel |
| `TS_KEY_EXPIRES` | — | Auth key expiry date |

## Tailscale Setup

Tailscale provides secure remote access so you can reach the launcher from your phone or any device on your tailnet.

1. Go to [Tailscale Admin → Settings → Keys](https://login.tailscale.com/admin/settings/keys)
2. Generate a **reusable** auth key tagged `tag:claude-launcher`
3. Set `TAILSCALE_AUTHKEY` and `TS_KEY_EXPIRES` in `.env`

For native setups, just run `tailscale login` on the machine.

## Usage

### The Dashboard

The launcher is a single-page app with two views:

**Main view** (everything on one screen):
- **Active Sessions** — Running and pending sessions at the top. Each shows an "Open in Claude" button with the session URL. Auto-hidden when empty.
- **Workspaces** — Your configured environments. Green = ready, red = needs attention.
- **Recent** — Collapsed section at the bottom with stopped/failed sessions. Expandable. Has a "Clear" button for bulk cleanup.

**Discover view** — Accessed via the "Discover" button in the top bar. Scans Docker containers and local repos, shows compatibility status, one-click add to workspaces.

### Starting a Session

1. Open the dashboard on your phone
2. Find your workspace (green pill = ready)
3. Tap **Launch** — starts immediately with a random label
4. Or tap **Options** to customize: set a label, branch, or toggle worktree mode
5. The session appears in Active Sessions with a progress indicator
6. When ready, tap **Open in Claude** — opens the real Claude app connected to your code

### Worktree Sessions

Check "Use worktree (isolated copy off main)" in the Options form. This passes `--spawn worktree` to `claude remote-control`, which creates isolated git worktrees for each session. Branches are auto-named like `wt/swift-fix` or `wt/bold-review`.

The launcher checks out `main` before starting so worktrees always branch off the default branch.

### Managing Sessions

- **Output** — Tap to see the raw `claude remote-control` output (ANSI-stripped)
- **Stop** — Sends SIGTERM (graceful shutdown, Claude deregisters from mobile app), then SIGKILL after 2 seconds if needed
- **Delete** — Removes the session record from the launcher
- **Clear** — Bulk-delete all ended sessions at once

### Workspace Health

Each workspace shows health status based on:
- Runtime accessible (container running / host reachable)
- Directory exists
- Git available
- Claude CLI found
- Authentication credentials present

If a workspace shows "Needs attention":
- **Fix** — Attempts auto-repair (e.g. accepting workspace trust via `claude -p`)
- **Recheck** — Re-runs health checks

### Auto-Discovery

Tap **Discover** in the top bar to scan your environment:

- **Compatible** (green) — Has Claude CLI, git, and auth. Ready to add.
- **Needs Setup** (yellow) — Missing one or more requirements.
- **Not Ready** (gray) — Containers that are stopped or lack most requirements.

Docker containers show Running/Stopped status with uptime. Local repos show as "Local". Tap **+ Add** to add any discovered environment to your workspaces.

## API Reference

All endpoints return JSON.

### Workspots

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/workspots` | List all configured workspots |
| `GET` | `/api/workspots/health` | Health report for each workspot |
| `POST` | `/api/workspots` | Add a new workspot (file-backed) |
| `DELETE` | `/api/workspots/{name}` | Remove a file-backed workspot |
| `POST` | `/api/workspots/{name}/recheck` | Re-run health for a single workspot |
| `POST` | `/api/workspots/{name}/fix` | Auto-fix workspace issues (trust, etc.) |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/sessions` | List all sessions (optional `?workspot=name` filter) |
| `GET` | `/api/sessions/{id}` | Get a single session |
| `GET` | `/api/sessions/{id}/output` | Get session output (optional `?tail=N`, default 50) |
| `GET` | `/api/sessions/live.json` | List only pending/running sessions |
| `POST` | `/api/sessions` | Start a new session |
| `POST` | `/api/sessions/{id}/kill` | Stop a running session (SIGTERM + SIGKILL) |
| `DELETE` | `/api/sessions/{id}` | Delete a session record |
| `DELETE` | `/api/sessions` | Bulk delete all stopped/failed sessions |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/servers` | List server records |
| `POST` | `/api/servers/{workspot}/ensure` | Reconcile a workspot's server |
| `GET` | `/api/discover` | Auto-discover potential workspaces |
| `GET` | `/status` | Quick status summary per workspot |
| `POST` | `/api/hooks/session-start` | Webhook for session URL callbacks |
| `POST` | `/kill` | Kill all sessions for a workspot |

### Starting a Session via API

```bash
curl -X POST http://localhost:8765/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"workspot": "my-project", "label": "auth-refactor", "worktree": true}'
```

Fields: `workspot` (required), `label` (string), `branch` (string), `worktree` (boolean), `directory` (string).

## Architecture

```
┌─────────────────────┐          ┌──────────────────────┐
│  Your Phone          │          │  Claude app           │
│  (Claude Launcher    │          │  (claude.ai / mobile) │
│   dashboard PWA)     │          │                      │
└─────────┬───────────┘          └──────────▲───────────┘
          │ tap "Launch"                    │ tap the URL
          │                                │
          │ Tailscale VPN                  │
┌─────────▼────────────────────────────────┼───────────┐
│  Claude Launcher (FastAPI)               │           │
│                                          │           │
│  ┌──────────────┐  ┌──────────────┐      │           │
│  │ SessionMgr   │  │ ServerMgr    │      │           │
│  │ (lifecycle)  │  │ (health/PID) │      │           │
│  └──────┬───────┘  └──────┬───────┘      │           │
│         │     ┌────────────┘             │           │
│  ┌──────▼─────▼─────────────────┐        │           │
│  │  Reconciler (background)     │        │           │
│  │  every 12s: check pending,   │        │           │
│  │  detect dead processes       │        │           │
│  └──────┬───────────────────────┘        │           │
│         │                                │           │
│  ┌──────▼───────────────────────┐        │           │
│  │  RuntimeManager              │        │           │
│  │  ┌─────────────┐ ┌────────┐  │        │           │
│  │  │DockerAdapter│ │HostAdpt│  │        │           │
│  │  └──────┬──────┘ └───┬────┘  │        │           │
│  └─────────┼─────────────┼──────┘        │           │
│            │             │               │           │
│  ┌─────────▼──┐  ┌──────▼────────┐      │           │
│  │docker exec │  │ local shell   │      │           │
│  │claude      │  │claude         │      │           │
│  │remote-ctrl │  │remote-ctrl    │──────┘           │
│  └────────────┘  └───────────────┘  returns URL     │
│                                                     │
│  Registry: /data/*.json (file-locked via fcntl)     │
│  Frontend: Preact + Signals (Vite build)            │
└─────────────────────────────────────────────────────┘
```

The launcher **never touches your conversations**. It only starts the `remote-control` process and captures the URL. All chat traffic flows directly between the Claude app and your environment.

### Key Modules

| Module | Role |
|--------|------|
| `main.py` | FastAPI routes, reconciler startup, static file serving |
| `config.py` | Loads and validates `.env` configuration |
| `models.py` | Pydantic models for workspots, sessions, servers, discovery |
| `runtime.py` | Docker and host runtime adapters (env isolation) |
| `session_manager.py` | Session creation, launch, kill, output, reconciliation |
| `server_manager.py` | Health checks, preflight validation, process tracking |
| `registry.py` | JSON-based persistence with file locking (fcntl) |
| `discovery.py` | Docker container + local repo scanning |
| `workspot_store.py` | File-backed workspot CRUD (add/remove from UI) |
| `hook_ingest.py` | Webhook handler for session callbacks |

### Frontend

The frontend has two implementations:

- **Preact + Signals** (`app/frontend/`) — TypeScript, component architecture, Vite build. 14 KB gzipped.
- **Legacy vanilla JS** (`app/static/index.html`) — Single-file fallback, no build step.

The server auto-detects which to serve: if `app/frontend/dist/` exists, it serves the built frontend. Otherwise, the legacy file.

## Logs and Troubleshooting

### Common Issues

**Session stays "pending"**
- The background reconciler checks every 12 seconds. If the URL appears in the output file, it auto-promotes to "running".
- If the output contains errors (trust, auth, etc.), it auto-marks as "failed".
- Check the session output via the "Output" button for details.

**"Needs attention" on a workspace**
- Tap **Fix** to attempt auto-repair (trust acceptance, etc.)
- Tap **Recheck** to re-run health checks after manual fixes
- Common causes: container not running, Claude CLI not installed, not authenticated

**Health check shows "not authenticated"**
Run `claude` interactively inside the container/host to complete authentication. The launcher checks for `~/.claude/.credentials.json`.

**Session not disappearing from Claude mobile app after kill**
- Clean kills (SIGTERM) trigger Claude's deregister. Session should disappear.
- Force kills (SIGKILL) skip cleanup. Session expires after 24 hours.

**Container not found**
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

### Stopping

```bash
# Native
pkill -f "uvicorn app.main"

# Docker
docker compose down          # Stop services
docker compose down -v       # Stop and remove volumes (clears all state)
```

## License

MIT
