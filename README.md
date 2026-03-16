# Claude Launcher

A self-hosted web tool that starts a `claude remote-control` session inside a running
devcontainer, accessible from your phone via Tailscale. Open the UI, tap a button, and get
a one-time URL to connect Claude on claude.ai directly to your dev environment.

---

## Prerequisites

- Docker + Docker Compose (v2)
- A running devcontainer with `claude` installed (e.g. `/home/node/.local/bin/claude`)
- A Tailscale account

---

## Setup

```bash
git clone <this-repo> claude-launcher
cd claude-launcher
cp .env.example .env
# Edit .env and fill in all values (see below)
docker compose up -d --build
```

---

## Finding Your Devcontainer Name

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

Copy the container name (e.g. `exxdev-carlos-app-1`) into `.env` as `DEVCONTAINER_NAME`.

The `WORKING_DIR` should be a directory inside that container where workspace trust has
already been accepted. Check `/home/node/.claude.json` for `hasTrustDialogAccepted: true`.

---

## Tailscale Setup

1. Go to [Tailscale Admin → Settings → Keys](https://login.tailscale.com/admin/settings/keys)
2. Generate a reusable auth key tagged `tag:claude-launcher`
3. Set `TAILSCALE_AUTHKEY` in `.env`
4. Set `TS_KEY_EXPIRES` to the key's expiry date (ISO format, e.g. `2026-06-05`) — the
   launcher will log a warning 14 days before it expires

Recommended ACL entry (lets your personal devices reach the launcher, not the other way):

```json
{
  "action": "accept",
  "src": ["autogroup:member"],
  "dst": ["tag:claude-launcher:8765"]
}
```

---

## Accessing the UI

After `docker compose up`, the UI is available at:

- **Local**: `http://localhost:8765` (bound to `127.0.0.1` by default)
- **Tailscale**: `http://<tailscale-ip>:8765` (e.g. `http://100.72.170.24:8765`)

Find your Tailscale IP in the [admin panel](https://login.tailscale.com/admin/machines).

### Buttons

- **Start Session** — reconnects to an existing `claude remote-control` process if one is
  running, otherwise starts a new one in `WORKING_DIR`
- **New Worktree Session** — creates a fresh git worktree under `/tmp/claude-worktrees/`
  with an auto-generated branch name (`wt-YYYYMMDD-xxxx`) and starts a separate session
  there. Useful for parallel isolated work.

---

## Rotating the Tailscale Auth Key

1. Generate a new key at [Tailscale Admin → Keys](https://login.tailscale.com/admin/settings/keys)
2. Update `TAILSCALE_AUTHKEY` and `TS_KEY_EXPIRES` in `.env`
3. Restart the stack:

```bash
docker compose down && docker compose up -d
```

> **Note:** Always bring the full stack down before recreating. Using `--force-recreate`
> on only the tailscale service breaks `network_mode: service:claude-launcher`.

---

## Logs / Stopping

```bash
# View logs
docker compose logs -f

# Stop
docker compose down

# Stop and remove volumes (clears session history and Tailscale state)
docker compose down -v
```
