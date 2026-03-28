# Claude Launcher — Agent & Contributor Context

This file is the authoritative source of context for AI agents and new contributors. Read this before touching code.

---

## Mission

Claude Launcher solves one problem: **getting from your phone to a Claude Code session in a real dev environment in a single tap**.

`claude remote-control` already handles everything complex — authentication, conversation state, tool use, the full Claude feature set. What's missing is a way to invoke it from a phone, pick the right workspace, and get back a URL the Claude mobile app can open. Claude Launcher is that missing piece.

It is a **session orchestrator**, not a chat interface. It deliberately avoids reimplementing any part of the Claude experience — no custom conversation UI, no terminal emulators, no replicated features. Just the session lifecycle: start → capture URL → open in Claude app.

---

## Who Uses This & How

**Primary persona:** A developer who spends 90%+ of their away-from-desk coding time on a phone. They have one or more dev machines (or devcontainers) running 24/7, and they want to spin up a Claude Code session in any of them from anywhere.

**Typical flow:**
1. Developer is on their couch, commuting, or in a meeting
2. Opens the Claude Launcher PWA on their phone (via Tailscale URL)
3. Taps **Launch** on a workspace
4. A URL appears — tap **Open in Claude**
5. The Claude mobile app opens, connected to the real dev environment
6. Full Claude Code session: code, review, debug — nothing is a simulation

**Secondary use:** Desktop convenience — bookmark the launcher, manage sessions across multiple workspaces, track what's running.

---

## Architecture

```
Phone → Tailscale VPN → Claude Launcher (FastAPI, port 8765) → RuntimeManager → claude remote-control
                                                                                        ↓
                                                                              URL → Claude app
```

The launcher **never touches conversations**. All chat traffic flows directly between the Claude app and your environment.

### Backend modules

| File | Responsibility |
|------|----------------|
| `app/main.py` | FastAPI routes (31 endpoints), reconciler startup, static file serving |
| `app/config.py` | Loads `.env`, validates `WORKSPOTS` JSON, builds `AppConfig` |
| `app/models.py` | Pydantic models: Workspot, SessionRecord, ServerRecord, DiscoveredEnvironment |
| `app/runtime.py` | `DockerRuntimeAdapter` (docker exec) + `HostRuntimeAdapter` (local shell) |
| `app/session_manager.py` | Session lifecycle: create → launch → poll for URL → reconcile |
| `app/server_manager.py` | Health checks (8 checks per workspot), preflight validation |
| `app/registry.py` | JSON persistence with `fcntl` file locking (handles concurrent requests) |
| `app/discovery.py` | Scans Docker containers + local git repos, scores by compatibility |
| `app/workspot_store.py` | File-backed CRUD for workspots added via UI |
| `app/hook_ingest.py` | Webhook endpoint for external session URL callbacks |

### Frontend modules

Built with **Preact + TypeScript + Signals**, bundled by Vite + Bun. ~14 KB gzipped.

| Path | Responsibility |
|------|----------------|
| `app/frontend/src/pages/DashboardPage.tsx` | Main view: active sessions, workspace grid, recent sessions |
| `app/frontend/src/pages/DiscoveryPage.tsx` | Discovery view: scan results grouped by compatibility |
| `app/frontend/src/components/WorkspaceCard.tsx` | Workspace card: health status, Launch/Options buttons, inline OptionsForm |
| `app/frontend/src/components/SessionCard.tsx` | Session card: status, progress steps, Open-in-Claude button, output panel |
| `app/frontend/src/components/OptionsForm.tsx` | Inline form within workspace card for label/branch/worktree options |
| `app/frontend/src/components/DiscoveryCard.tsx` | Discovery result: compatibility badge, issues, Add button |
| `app/frontend/src/components/ProgressSteps.tsx` | Visual launch progress (pending → spawning → waiting for URL) |
| `app/frontend/src/state/signals.ts` | Global reactive state via Preact Signals |
| `app/frontend/src/state/polling.ts` | Polling loop (every 3-5s when live sessions exist) |
| `app/frontend/src/api/` | HTTP client wrappers per resource type |
| `app/frontend/src/app.css` | All styles (design tokens, component styles, responsive breakpoints) |

**Fallback:** `app/static/index.html` is a single-file vanilla JS frontend with no build step. The server auto-detects: if `app/frontend/dist/` exists → Preact build; otherwise → legacy fallback.

---

## Development Context

The `feature/smart-discovery` branch is the primary working branch. It is a complete rewrite from a single-file monolith (`main.py`, ~560 lines) to the current modular architecture. Treat this branch as the production code — `origin/main` is the old monolith.

**What is built and working:**
- Multi-workspot dashboard (Docker containers + host runtimes)
- Session lifecycle with 12-second background reconciliation
- Auto-discovery scanning with compatibility scoring
- File-backed workspot store (add/remove via UI)
- Preact + Signals frontend (Dashboard + Discovery pages)
- Systemd user service for auto-start on boot
- Full API (31 endpoints)

**Active development area:** Smart discovery UX improvements — scoring refinements, filtering, better onboarding for freshly discovered workspaces.

---

## Key Design Decisions & Rationale

### "Thin orchestrator" philosophy
This app does not render Claude conversations, provide a terminal, or stream Claude output. It invokes `claude remote-control` and captures the URL. This keeps the surface area small and ensures users get the latest Claude features without any lag or reimplementation.

### Polling vs. webhooks
Claude remote-control doesn't have a stable callback mechanism. The launcher polls the session output file every 12 seconds to detect when a URL appears. A webhook endpoint also exists (`/api/hooks/session-start`) — if an external script can push the URL back, it's faster. Both mechanisms can coexist.

### File-based registry with fcntl locking
SQLite or Redis would be overkill. The JSON registry with file-level locking is simple, portable, and crash-safe. The tradeoff is no atomic cross-record transactions, which the use case doesn't require.

### Two-frontend architecture
The Preact build is the primary frontend. The vanilla JS fallback in `app/static/` exists for cases where the build isn't available (e.g., first clone without running `bun install && bun run build`). Most users will always run the Preact build.

### Environment isolation for Docker runtimes
`LOCAL_CLAUDE_HOME` and `LOCAL_CLAUDE_XDG_DATA_HOME` provide a separate HOME for the launcher's own Claude process. This prevents the launcher's credentials from leaking into workspot containers when the launcher itself runs inside Docker.

---

## Mobile-First Design Philosophy

90% of real usage is on a phone. The UI is designed around that constraint.

- **48px minimum tap targets** (`--tap: 48px`) on all interactive elements
- **Single-column layout** by default, expands to 2→3 columns on larger screens
- **Sticky top bar** with frosted-glass blur so navigation is always reachable
- **Optimistic UI** — the pending session card appears immediately on tap, before the API responds
- **Auto-scroll to top** when a session starts so the pending card is immediately visible
- **"Open in Claude" is a full-width green button** — the most important action gets the most real estate
- **Relative timestamps** ("3m ago") — readable at a glance, no date parsing on a small screen
- **Auto-scan on Discovery** — no extra tap to start scanning
- **Dark navy theme** — phone screens are often viewed in low-light environments

---

## Current Design System

All design tokens and component styles are in `app/frontend/src/app.css`.

**Color tokens:**
| Token | Value | Used for |
|-------|-------|----------|
| `--bg` | `#0b1220` | Page background |
| `--surface` | `rgba(15, 23, 42, 0.92)` | Cards and panels |
| `--surface-2` | `rgba(30, 41, 59, 0.9)` | Code path display, secondary surfaces |
| `--accent` | `#60a5fa` | Primary actions, focus rings, links |
| `--green` | `#22c55e` | Running sessions, healthy workspaces, "Open in Claude" button |
| `--yellow` | `#f59e0b` | Pending sessions, warnings, progress indicators |
| `--red` | `#f87171` | Failed sessions, error states, danger actions |
| `--muted` | `#94a3b8` | Secondary text, labels, metadata |
| `--text` | `#e5eefc` | Primary text |
| `--border` | `rgba(148, 163, 184, 0.18)` | Card borders |

**Layout:**
- Max width: 960px, centered
- Mobile padding: 12px; desktop: 16px
- Grid: 1 column (mobile) → 2 columns (720px+) → 3 columns (1000px+)
- Card border-radius: 16px (`--r`)
- Small element radius: 12px (`--r-sm`)

**Component tree:**
```
App
├── TopBar (sticky, frosted-glass)
│   ├── Brand (title + subtitle)
│   └── Actions (Discover button)
└── Page
    ├── DashboardPage
    │   ├── ActiveSessions        (hidden when empty; auto-visible on launch)
    │   │   └── SessionCard[]     (pending/running)
    │   ├── WorkspaceGrid
    │   │   └── WorkspaceCard[]
    │   │       └── OptionsForm   (inline expand, not a modal)
    │   └── RecentSessions        (collapsible; has bulk-clear button)
    │       └── SessionCard[]     (stopped/failed)
    └── DiscoveryPage
        ├── Panel: Compatible     (green pill count)
        ├── Panel: Needs Setup    (yellow pill count)
        └── Panel: Not Ready      (gray pill count)
```

**Session card visual states:**
| Status | Border | Other |
|--------|--------|-------|
| `pending` | `rgba(245, 158, 11, 0.25)` (yellow) | Spinner icon + ProgressSteps component |
| `running` | `rgba(34, 197, 94, 0.25)` (green) | Full-width "Open in Claude" green button |
| `stopped` / `failed` | Default | 60% opacity; lives in RecentSessions |

**Key interaction flows:**
1. **Quick launch:** Tap "Launch" → optimistic pending card inserted at top of list → page scrolls to top → API call → session goes running → "Open in Claude" button appears
2. **Options launch:** Tap "Options" → OptionsForm expands inline within the workspace card → set label/branch/worktree toggle → tap "Start with options"
3. **Stop:** Tap "Stop" → optimistic status update → SIGTERM sent → SIGKILL fallback after 2s → session moves to Recent
4. **Discovery:** Tap "Discover" in TopBar → auto-scan starts → results grouped by compatibility → tap "+ Add" on any environment

---

## Known Limitations

1. **Reconciliation latency** — Up to 12s delay between when `claude remote-control` outputs a URL and when the launcher promotes the session to "running". Webhooks via `/api/hooks/session-start` are faster.

2. **PID loss on restart** — Running sessions lose their PID tracking if the launcher restarts. They continue running in the background but can't be killed via the UI.

3. **Discovery performance** — Scanning many containers or deep directory trees can take up to 15s. Limited to 5 parallel async Docker scans.

4. **Worktree cleanup** — Force-killed worktree sessions may leave orphaned git worktrees.

5. **Auth check path** — Health checks look for `~/.claude/.credentials.json`. Non-standard auth setups may show as unauthenticated.

---

## Development Setup

```bash
# Backend
pip install fastapi uvicorn python-dotenv
cp .env.example .env  # edit as needed
python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload

# Frontend (build once or run dev server)
cd app/frontend
bun install
bun run build      # produces app/frontend/dist/ — served by FastAPI
bun run dev        # Vite dev server on :5173, proxies API to :8765
```

**Data directory:** The default paths (`/data/*.json`) are for Docker deployments. For native installs, set:
```
SESSION_REGISTRY_FILE=./data/session-registry.json
SESSION_HISTORY_FILE=./data/sessions.json
WORKSPOT_CONFIG_FILE=./data/workspots.json
```
