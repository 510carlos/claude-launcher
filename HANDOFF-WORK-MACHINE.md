# Claude Launcher — New Machine Installation Handoff

This document is for an AI agent setting up Claude Launcher on a **new machine** (Raspberry Pi, WSL, or any Linux host). The repo is at `https://github.com/510carlos/claude-launcher.git` on the `main` branch.

**Prerequisites:** The machine should already have `python3`, `node` (via nvm), the `claude` CLI, and Tailscale installed and configured.

---

## What This App Does

Claude Launcher is a FastAPI + Preact PWA that starts `claude remote-control` sessions and captures the URL so you can open them in the Claude mobile app. It runs as a systemd user service on port 8765, accessed over Tailscale.

---

## Step-by-Step Installation

### 1. Clone the repo

```bash
cd ~
git clone https://github.com/510carlos/claude-launcher.git
cd claude-launcher
```

### 2. Install uv (Python package runner)

[uv](https://docs.astral.sh/uv/) handles dependencies automatically — no venv to create or manage.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc  # or: export PATH="$HOME/.local/bin:$PATH"
```

### 3. Install bun (if not present) and build frontend

```bash
# Install bun if not already installed:
curl -fsSL https://bun.sh/install | bash
source ~/.zshrc  # or: export PATH="$HOME/.bun/bin:$PATH"

cd app/frontend
bun install
bun run build
cd ../..
```

### 4. Install devcontainer CLI (optional, for devcontainer support)

```bash
npm install -g @devcontainers/cli
```

### 5. Create the data directory and `.env` file

```bash
mkdir -p data
```

Create `/home/<user>/claude-launcher/.env` with these contents. **Adjust paths for the actual user and machine:**

```env
APP_NAME=Work
PORT=8765

DB_FILE=/home/<user>/claude-launcher/data/launcher.db
SESSION_REGISTRY_FILE=/home/<user>/claude-launcher/data/session-registry.json
SESSION_HISTORY_FILE=/home/<user>/claude-launcher/data/sessions.json
WORKSPOT_CONFIG_FILE=/home/<user>/claude-launcher/data/workspots.json
DISCOVERY_SCAN_DIRS=~
DISCOVERY_DOCKER_ENABLED=false

LOCAL_CLAUDE_HOME=/home/<user>
LOCAL_CLAUDE_XDG_DATA_HOME=/home/<user>/.local/share

# Seed workspots — add the main workspace(s) on this machine
WORKSPOTS=[{"name":"<repo-name>","dir":"/home/<user>/<repo-path>"}]
```

Key differences from home machine:
- `APP_NAME=Work` (shows "Work" in the top bar and "Work - CL" on phone home screen)
- `DISCOVERY_SCAN_DIRS=~` will auto-discover git repos under home
- Set `DISCOVERY_DOCKER_ENABLED=true` if Docker containers are used on this machine

### 6. Create the systemd user service

Create `~/.config/systemd/user/claude-launcher.service`:

```ini
[Unit]
Description=Claude Launcher — phone-first remote dev session manager
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/<user>/claude-launcher
EnvironmentFile=-/home/<user>/claude-launcher/.env
Environment=PATH=/home/<user>/.nvm/versions/node/<node-version>/bin:/home/<user>/.local/bin:/home/<user>/.bun/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/<user>/.local/bin/uv run --with fastapi --with uvicorn --with python-dotenv --with pydantic python -m uvicorn app.main:app --host 0.0.0.0 --port 8765
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

**Important:** The PATH must include:
- The directory containing `claude` CLI (usually `~/.local/bin`)
- The directory containing `node` (usually under `~/.nvm/versions/node/<version>/bin`)
- The directory containing `bun` (usually `~/.bun/bin`)

Find the correct paths with:
```bash
which claude
which node
which bun
```

### 7. Enable and start the service

```bash
systemctl --user daemon-reload
systemctl --user enable claude-launcher
systemctl --user start claude-launcher
loginctl enable-linger $(whoami)   # keeps service running after SSH disconnect
```

### 8. Verify it's running

```bash
systemctl --user status claude-launcher
curl http://localhost:8765/api/config
curl http://localhost:8765/api/workspots
curl http://localhost:8765/api/workspots/health
```

### 9. Set up Tailscale HTTPS access

```bash
sudo tailscale serve --bg 8765
```

This exposes the launcher at `https://<hostname>.tail<tailnet>.ts.net`. The user can then bookmark or Add to Home Screen on their phone.

---

## Architecture Quick Reference

| Component | Path |
|-----------|------|
| Backend (FastAPI) | `app/main.py` — routes, startup |
| Config | `app/config.py` — loads `.env` |
| Database | `app/db.py` — SQLite with WAL mode |
| Registry | `app/registry.py` — session/server CRUD |
| Session lifecycle | `app/session_manager.py` |
| Health checks | `app/server_manager.py` |
| Runtime adapters | `app/runtime.py` — host, docker, devcontainer |
| Discovery | `app/discovery.py` — scans for git repos |
| Frontend build | `app/frontend/dist/` — served by FastAPI |
| Data directory | `data/launcher.db` — SQLite database |

---

## Verification Checklist

After installation, verify these work:

- [ ] `curl http://localhost:8765/` returns HTML
- [ ] `curl http://localhost:8765/api/config` returns `{"app_name": "Work"}`
- [ ] `curl http://localhost:8765/api/workspots` lists the configured workspaces
- [ ] `curl http://localhost:8765/api/workspots/health` shows all checks passing
- [ ] `curl http://localhost:8765/api/discover` finds git repos
- [ ] The Tailscale HTTPS URL is accessible from the phone
- [ ] Launching a session produces a Claude URL that opens in the Claude app

---

## Troubleshooting

**Service won't start:**
```bash
journalctl --user -u claude-launcher --no-pager -n 30
```

**Claude CLI not found:** Check the PATH in the systemd service includes the directory from `which claude`.

**Port already in use:** Check with `lsof -i :8765` and kill the existing process.

**Health checks fail with "Not authenticated":** Run `claude login` on the machine.

**Frontend shows old version:** Run `cd app/frontend && bun run build` then `systemctl --user restart claude-launcher`.

**Updates from phone:** The Updates page (tap "Updates" in top bar) can pull latest from GitHub and restart the service remotely.
