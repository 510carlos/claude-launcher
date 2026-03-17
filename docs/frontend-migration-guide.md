# Frontend Migration Guide: Vanilla JS → Preact + Signals

> Step-by-step implementation guide. Each phase leaves the app working.
>
> **Stack:** Bun (package manager/runtime) + Vite (build tool) + Preact (UI) + Signals (state)
>
> **Pre-read:** [frontend-architecture.md](frontend-architecture.md) for the rationale behind these choices.

---

## Phase 0: Scaffolding

**Goal:** Preact app renders "Hello" and `/api/*` proxies to FastAPI. Zero UI migration yet.

### Step 0.1: Create the frontend directory

```bash
mkdir -p app/frontend
cd app/frontend
```

### Step 0.2: Initialize with Bun

```bash
bun init -y
```

### Step 0.3: Install dependencies

```bash
bun add preact @preact/signals
bun add -d vite @preact/preset-vite typescript
```

### Step 0.4: Create `tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "jsxImportSource": "preact",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "paths": {
      "react": ["./node_modules/preact/compat/"],
      "react-dom": ["./node_modules/preact/compat/"]
    }
  },
  "include": ["src"]
}
```

### Step 0.5: Create `vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

export default defineConfig({
  plugins: [preact()],
  root: '.',
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8765',
      '/status': 'http://localhost:8765',
      '/start': 'http://localhost:8765',
      '/start-worktree': 'http://localhost:8765',
      '/kill': 'http://localhost:8765',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
```

### Step 0.6: Create `index.html` (Vite entry point)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta name="theme-color" content="#0f172a">
  <link rel="manifest" href="/manifest.json">
  <link rel="apple-touch-icon" href="/icon-192.png">
  <title>Claude Launcher</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

### Step 0.7: Create `src/main.tsx`

```tsx
import { render } from 'preact';

function App() {
  return <h1>Claude Launcher (Preact)</h1>;
}

render(<App />, document.getElementById('app')!);
```

### Step 0.8: Copy static assets

```bash
cp ../static/manifest.json ./public/manifest.json
cp ../static/icon-192.png ./public/icon-192.png
cp ../static/icon-512.png ./public/icon-512.png
cp ../static/sw.js ./public/sw.js
```

### Step 0.9: Add scripts to `package.json`

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit"
  }
}
```

### Step 0.10: Verify

```bash
# Terminal 1: Start FastAPI backend
cd /home/carlos/git/claude-launcher && uvicorn app.main:app --port 8765

# Terminal 2: Start Vite dev server
cd app/frontend && bun run dev
```

Open `http://localhost:3000` — should see "Claude Launcher (Preact)".
Open `http://localhost:3000/api/workspots` — should proxy to FastAPI and return JSON.

---

## Phase 1: Extract Non-UI Code

**Goal:** Types, API layer, state signals, and polling all working. Still rendering "Hello" but state is populated.

### Step 1.1: Create `src/types.ts`

Mirror the Python models. These are the shapes returned by the API.

```typescript
// Mirrors: app/models.py — keep in sync

export type RuntimeType = 'docker' | 'host';
export type WorkspotSource = 'env' | 'file';
export type SessionStatus = 'pending' | 'running' | 'stopped' | 'failed';
export type ServerStatus = 'unknown' | 'running' | 'stopped' | 'unhealthy';

export interface Workspace {
  name: string;
  runtime: RuntimeType;
  container: string | null;
  dir: string;
  claude_bin: string;
  server_capacity: number;
  source: WorkspotSource;
}

export interface HealthStatus {
  workspot: string;
  runtime_ok: boolean;
  repo_exists: boolean;
  git_ok: boolean;
  claude_bin_ok: boolean;
  auth_ok: boolean;
  server_status: ServerStatus;
  issues: string[];
}

export interface Session {
  id: string;
  workspot: string;
  server_key: string;
  label: string;
  runtime: RuntimeType;
  container: string | null;
  repo_root: string;
  working_dir: string;
  branch: string | null;
  worktree_path: string | null;
  url: string | null;
  status: SessionStatus;
  created_at: string;
  last_seen_at: string | null;
  source: string;
  server_session_name: string | null;
  output_file: string | null;
  metadata: Record<string, unknown>;
}

export interface DiscoveredEnvironment {
  name: string;
  runtime: RuntimeType;
  dir: string;
  container: string | null;
  claude_bin: string | null;
  compatibility: 'compatible' | 'partial' | 'incompatible';
  checks: Record<string, boolean>;
  issues: string[];
  already_configured: boolean;
  image: string | null;
  container_status: string | null;
}

export interface DiscoveryResult {
  total: number;
  compatible: DiscoveredEnvironment[];
  partial: DiscoveredEnvironment[];
  incompatible: DiscoveredEnvironment[];
}

export interface StartSessionRequest {
  workspot: string;
  worktree?: boolean;
  label?: string;
  branch?: string;
  directory?: string | null;
}

export interface ApiResponse {
  status: 'ok' | 'error';
  message?: string;
  url?: string;
  [key: string]: unknown;
}
```

### Step 1.2: Create `src/api/client.ts`

```typescript
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers as Record<string, string> },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }
  return res.json();
}
```

### Step 1.3: Create `src/api/sessions.ts`

```typescript
import { api } from './client';
import type { Session, StartSessionRequest, ApiResponse } from '../types';

export const listSessions = (workspot?: string) =>
  api<Session[]>(workspot ? `/api/sessions?workspot=${encodeURIComponent(workspot)}` : '/api/sessions');

export const getSession = (id: string) =>
  api<Session>(`/api/sessions/${id}`);

export const startSession = (req: StartSessionRequest) =>
  api<ApiResponse>('/api/sessions', { method: 'POST', body: JSON.stringify(req) });

export const killSession = (id: string) =>
  api<ApiResponse>(`/api/sessions/${id}/kill`, { method: 'POST' });

export const deleteSession = (id: string) =>
  api<ApiResponse>(`/api/sessions/${id}`, { method: 'DELETE' });

export const deleteEndedSessions = () =>
  api<ApiResponse>('/api/sessions', { method: 'DELETE' });

export const getSessionOutput = (id: string, tail = 80) =>
  api<{ status: string; output?: string }>(`/api/sessions/${id}/output?tail=${tail}`);
```

### Step 1.4: Create `src/api/workspaces.ts`

```typescript
import { api } from './client';
import type { Workspace, HealthStatus, ApiResponse } from '../types';

export const listWorkspaces = () =>
  api<Workspace[]>('/api/workspots');

export const getHealth = () =>
  api<HealthStatus[]>('/api/workspots/health');

export const fixWorkspot = (name: string) =>
  api<ApiResponse & { fixes?: string[]; health?: HealthStatus }>(
    `/api/workspots/${encodeURIComponent(name)}/fix`, { method: 'POST' }
  );

export const recheckWorkspot = (name: string) =>
  api<HealthStatus>(
    `/api/workspots/${encodeURIComponent(name)}/recheck`, { method: 'POST' }
  );

export const addWorkspot = (data: {
  name: string; runtime: string; dir: string;
  container?: string | null; claude_bin?: string;
  server_capacity?: number; env?: Record<string, string>;
}) => api<ApiResponse>('/api/workspots', { method: 'POST', body: JSON.stringify(data) });

export const removeWorkspot = (name: string) =>
  api<ApiResponse>(`/api/workspots/${encodeURIComponent(name)}`, { method: 'DELETE' });
```

### Step 1.5: Create `src/api/discovery.ts`

```typescript
import { api } from './client';
import type { DiscoveryResult } from '../types';

export const runDiscovery = () =>
  api<DiscoveryResult>('/api/discover');
```

### Step 1.6: Create `src/state/signals.ts`

```typescript
import { signal, computed } from '@preact/signals';
import type { Workspace, Session, HealthStatus, DiscoveryResult } from '../types';

// Core data
export const workspaces = signal<Workspace[]>([]);
export const sessions = signal<Session[]>([]);
export const health = signal<HealthStatus[]>([]);

// Derived
export const activeSessions = computed(() =>
  sessions.value
    .filter(s => s.status === 'running' || s.status === 'pending')
    .sort((a, b) => {
      const w: Record<string, number> = { running: 0, pending: 1 };
      return (w[a.status] ?? 9) - (w[b.status] ?? 9)
        || new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    })
);

export const endedSessions = computed(() =>
  sessions.value
    .filter(s => s.status === 'stopped' || s.status === 'failed')
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
);

export const activeCount = computed(() => activeSessions.value.length);

// UI state
export const route = signal<'/' | '/discover'>('/');
export const notices = signal<{ id: number; msg: string; kind: 'info' | 'error' }[]>([]);
export const discoveryResult = signal<DiscoveryResult | null>(null);
export const scanning = signal(false);
export const recentOpen = signal(false);
export const optionsWorkspace = signal<string | null>(null);

// Progress phase tracking for pending sessions
export const pendingPhases = signal<Record<string, { phase: number; startedAt: number }>>({});

// Helpers
export function healthOf(name: string): HealthStatus | undefined {
  return health.value.find(h => h.workspot === name);
}

export function isHealthy(ws: Workspace): boolean {
  const h = healthOf(ws.name);
  return !!(h && h.runtime_ok && h.repo_exists && h.git_ok && h.claude_bin_ok && h.auth_ok);
}

let _noticeId = 0;
export function showNotice(msg: string, kind: 'info' | 'error' = 'info') {
  const id = ++_noticeId;
  notices.value = [...notices.value, { id, msg, kind }];
  if (kind === 'info') {
    setTimeout(() => {
      notices.value = notices.value.filter(n => n.id !== id);
    }, 4000);
  }
}

export function dismissNotice(id: number) {
  notices.value = notices.value.filter(n => n.id !== id);
}
```

### Step 1.7: Create `src/state/polling.ts`

```typescript
import { listWorkspaces, getHealth } from '../api/workspaces';
import { listSessions } from '../api/sessions';
import { workspaces, sessions, health, activeSessions } from './signals';

let timer: ReturnType<typeof setTimeout> | null = null;
let lastHash = '';

function hashState(ws: unknown[], h: unknown[], s: unknown[]) {
  return JSON.stringify([ws, h, s]);
}

export async function refresh(): Promise<boolean> {
  const [ws, hl, ss] = await Promise.all([
    listWorkspaces(), getHealth(), listSessions(),
  ]);
  const hash = hashState(ws, hl, ss);
  if (hash === lastHash) return false;
  lastHash = hash;
  workspaces.value = ws;
  health.value = hl;
  sessions.value = ss;

  // Cache for instant next load
  try {
    localStorage.setItem('launcher-cache', JSON.stringify({ workspaces: ws, health: hl, sessions: ss }));
  } catch {}

  return true;
}

export function loadFromCache() {
  try {
    const cached = localStorage.getItem('launcher-cache');
    if (cached) {
      const data = JSON.parse(cached);
      workspaces.value = data.workspaces || [];
      health.value = data.health || [];
      sessions.value = data.sessions || [];
    }
  } catch {}
}

export function startPolling() {
  const poll = async () => {
    try { await refresh(); } catch (e) { console.error('Poll failed:', e); }
    const fast = activeSessions.value.some(s => s.status === 'pending');
    timer = setTimeout(poll, fast ? 3000 : 15000);
  };
  poll();
}

export function stopPolling() {
  if (timer) { clearTimeout(timer); timer = null; }
}
```

### Step 1.8: Create `src/utils.ts`

```typescript
export function fmtTime(v: string | null | undefined): string {
  if (!v) return '\u2014';
  const d = new Date(v);
  if (isNaN(d.getTime())) return v;
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`;
  return d.toLocaleDateString();
}

export function sessionIdentity(workspot: string, branch: string | null): string {
  return branch ? `${workspot} / ${branch}` : workspot;
}

const _adj = ['swift','bold','calm','keen','warm','cool','bright','sharp','quick','fresh','neat','wise','glad','fair','prime'];
const _noun = ['fix','patch','review','draft','spike','task','build','scan','check','tweak','pass','sync','push','test','ship'];

export function randomLabel(): string {
  return _adj[Math.random() * _adj.length | 0] + '-' + _noun[Math.random() * _noun.length | 0];
}

export function randomBranch(): string {
  return 'wt/' + randomLabel();
}
```

### Step 1.9: Verify phase 1

Update `src/main.tsx` temporarily to prove state is loading:

```tsx
import { render } from 'preact';
import { workspaces, sessions, activeCount } from './state/signals';
import { loadFromCache, startPolling } from './state/polling';

loadFromCache();
startPolling();

function App() {
  return (
    <div>
      <h1>Claude Launcher (Preact)</h1>
      <p>{workspaces.value.length} workspaces, {activeCount.value} active</p>
      <pre>{JSON.stringify(sessions.value.slice(0, 2), null, 2)}</pre>
    </div>
  );
}

render(<App />, document.getElementById('app')!);
```

Verify data loads from FastAPI via the Vite proxy.

---

## Phase 2: Build Components Bottom-Up

**Goal:** All 13 components built and rendering. Matches current UI functionality.

Build in this order (each depends only on previously built components):

### Step 2.1: `src/components/HealthPill.tsx`

Stateless. Takes `health: HealthStatus | undefined`, renders the green/red/unknown pill.

### Step 2.2: `src/components/ProgressSteps.tsx`

Takes `sessionId: string`. Reads from `pendingPhases` signal. Manages its own setTimeout for phase advancement. Renders 3-step progress with bar.

### Step 2.3: `src/components/SessionCard.tsx`

Takes `session: Session`. Renders differently for active (with Open in Claude button, progress, stop) vs ended (with delete). Uses `ProgressSteps` for pending sessions.

### Step 2.4: `src/components/OptionsForm.tsx`

Takes `workspotName: string`, `onStart: (label, branch, worktree) => void`, `onCancel: () => void`. Local form state for label/branch/worktree inputs.

### Step 2.5: `src/components/WorkspaceCard.tsx`

Takes `workspace: Workspace`. Reads health from signal. Renders card with `HealthPill`, Launch button, Options button, error list, `OptionsForm`.

### Step 2.6: `src/components/ActiveSessions.tsx`

Reads `activeSessions` computed signal. Maps to `SessionCard` components. Hidden when empty.

### Step 2.7: `src/components/WorkspaceGrid.tsx`

Reads `workspaces` signal. Sorts by health. Maps to `WorkspaceCard` components. Shows empty state when no workspaces.

### Step 2.8: `src/components/RecentSessions.tsx`

Reads `endedSessions` computed signal. Collapsible via `recentOpen` signal. Maps to `SessionCard`. Clear all button.

### Step 2.9: `src/components/TopBar.tsx`

Reads `workspaces` and `activeCount` signals. Renders brand, summary, discover button.

### Step 2.10: `src/components/NoticeToast.tsx`

Reads `notices` signal. Renders info/error toasts. Auto-dismiss handled by the signal helper.

### Step 2.11: `src/components/DiscoveryCard.tsx`

Takes `env: DiscoveredEnvironment`. Renders checks, issues, add button.

### Step 2.12: `src/pages/DashboardPage.tsx`

Composes: `ActiveSessions` + `WorkspaceGrid` + `RecentSessions`.

### Step 2.13: `src/pages/DiscoveryPage.tsx`

Reads `discoveryResult` and `scanning` signals. Renders categorized `DiscoveryCard` lists. Scan button.

---

## Phase 3: Assemble the App

### Step 3.1: `src/app.tsx`

```tsx
import { route } from './state/signals';
import { TopBar } from './components/TopBar';
import { NoticeToast } from './components/NoticeToast';
import { DashboardPage } from './pages/DashboardPage';
import { DiscoveryPage } from './pages/DiscoveryPage';

export function App() {
  return (
    <div class="app">
      <TopBar />
      <NoticeToast />
      {route.value === '/' ? <DashboardPage /> : <DiscoveryPage />}
    </div>
  );
}
```

### Step 3.2: `src/main.tsx` (final)

```tsx
import { render } from 'preact';
import { App } from './app';
import { loadFromCache, startPolling } from './state/polling';
import { route } from './state/signals';
import './app.css';

// Hash routing
function syncRoute() {
  const h = (window.location.hash || '#/').replace(/^#/, '');
  route.value = h === '/discover' ? '/discover' : '/';
}
window.addEventListener('hashchange', syncRoute);
syncRoute();

// Refresh on visibility change (returning from Claude app)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    import('./state/polling').then(m => m.refresh().catch(() => {}));
  }
});

// Service worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

// Boot
loadFromCache();
render(<App />, document.getElementById('app')!);
startPolling();
```

### Step 3.3: `src/app.css`

Copy the CSS from the current `index.html` `<style>` block. The CSS variables, component styles, and responsive breakpoints all stay. Just move them to this file.

---

## Phase 4: Build Integration

### Step 4.1: Update FastAPI to serve built frontend

In `app/main.py`, update the static file serving to look for the Vite build output:

```python
# Check for built frontend first, fall back to legacy static/
BUILD_DIR = APP_DIR / "frontend" / "dist"
if BUILD_DIR.exists():
    app.mount("/assets", StaticFiles(directory=BUILD_DIR / "assets"), name="assets")

    @app.get("/")
    @app.get("/sessions")
    @app.get("/{path:path}")
    async def serve_spa(path: str = ""):
        spa_index = BUILD_DIR / "index.html"
        if spa_index.exists():
            return FileResponse(spa_index)
        return FileResponse(STATIC_DIR / "index.html")
else:
    # Legacy: serve old index.html
    @app.get("/")
    @app.get("/sessions")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")
```

### Step 4.2: Update Vite build output

In `vite.config.ts`, set the output directory:

```typescript
build: {
  outDir: 'dist',
  emptyOutDir: true,
},
```

### Step 4.3: Update Dockerfile

```dockerfile
# Stage 1: Build frontend
FROM oven/bun:1.3-slim AS frontend
WORKDIR /build
COPY app/frontend/package.json app/frontend/bun.lock* ./
RUN bun install --frozen-lockfile
COPY app/frontend/ .
RUN bun run build

# Stage 2: Python app
FROM python:3.12-slim
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY app/requirements.txt .
RUN pip install -r requirements.txt
COPY app/ ./app/
# Copy built frontend
COPY --from=frontend /build/dist/ ./app/frontend/dist/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
```

### Step 4.4: Update `.gitignore`

```
# Frontend build artifacts
app/frontend/node_modules/
app/frontend/dist/
app/frontend/.vite/
```

### Step 4.5: Verify production build

```bash
cd app/frontend && bun run build
# Check dist/ has index.html + assets/
ls dist/

# Start FastAPI with built frontend
cd /home/carlos/git/claude-launcher
uvicorn app.main:app --port 8765
# Open http://localhost:8765 — should serve the Preact app
```

---

## Phase 5: Polish

### Step 5.1: Remove old `index.html`

Once everything works, remove `app/static/index.html`. Keep `app/static/` for icons, manifest, and service worker (or migrate those into the Vite public directory too).

### Step 5.2: Type checking in CI

Add to `package.json`:
```json
"scripts": {
  "typecheck": "tsc --noEmit",
  "lint": "tsc --noEmit"
}
```

### Step 5.3: Consider `vite-plugin-pwa`

For proper service worker generation with precaching:

```bash
bun add -d vite-plugin-pwa
```

```typescript
// vite.config.ts
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    preact(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Claude Launcher',
        short_name: 'Claude',
        theme_color: '#0f172a',
        background_color: '#0a0a0a',
        display: 'standalone',
        orientation: 'portrait',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any maskable' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg}'],
        runtimeCaching: [
          {
            urlPattern: /^\/api\//,
            handler: 'NetworkFirst',
            options: { networkTimeoutSeconds: 3, cacheName: 'api-cache' },
          },
        ],
      },
    }),
  ],
});
```

This replaces the hand-written `sw.js` with a properly generated service worker.

---

## API Endpoint Reference

Every endpoint the frontend calls, for mapping to the API layer:

| Frontend API function | Method | Endpoint | Python route |
|----------------------|--------|----------|-------------|
| `listWorkspaces()` | GET | `/api/workspots` | `list_workspots` |
| `getHealth()` | GET | `/api/workspots/health` | `list_workspot_health` |
| `fixWorkspot(name)` | POST | `/api/workspots/{name}/fix` | `fix_workspot` |
| `recheckWorkspot(name)` | POST | `/api/workspots/{name}/recheck` | `recheck_workspot` |
| `addWorkspot(data)` | POST | `/api/workspots` | `add_workspot` |
| `removeWorkspot(name)` | DELETE | `/api/workspots/{name}` | `remove_workspot` |
| `listSessions(workspot?)` | GET | `/api/sessions` | `get_sessions` |
| `getSession(id)` | GET | `/api/sessions/{id}` | `get_session` |
| `startSession(req)` | POST | `/api/sessions` | `start_session` |
| `killSession(id)` | POST | `/api/sessions/{id}/kill` | `kill_session_by_id` |
| `deleteSession(id)` | DELETE | `/api/sessions/{id}` | `delete_session` |
| `deleteEndedSessions()` | DELETE | `/api/sessions` | `delete_ended_sessions` |
| `getSessionOutput(id)` | GET | `/api/sessions/{id}/output` | `get_session_output` |
| `runDiscovery()` | GET | `/api/discover` | `discover_environments` |

---

## Estimated File Count & Sizes After Migration

```
src/
  main.tsx              ~30 lines
  app.tsx               ~20 lines
  app.css               ~350 lines (moved from index.html)
  types.ts              ~80 lines
  utils.ts              ~30 lines
  state/
    signals.ts          ~70 lines
    polling.ts          ~50 lines
  api/
    client.ts           ~15 lines
    sessions.ts         ~25 lines
    workspaces.ts       ~30 lines
    discovery.ts        ~5 lines
  components/
    TopBar.tsx          ~25 lines
    NoticeToast.tsx     ~20 lines
    ActiveSessions.tsx  ~25 lines
    SessionCard.tsx     ~70 lines
    WorkspaceGrid.tsx   ~35 lines
    WorkspaceCard.tsx   ~80 lines
    RecentSessions.tsx  ~40 lines
    DiscoveryCard.tsx   ~60 lines
    ProgressSteps.tsx   ~50 lines
    HealthPill.tsx      ~20 lines
    OptionsForm.tsx     ~50 lines
  pages/
    DashboardPage.tsx   ~20 lines
    DiscoveryPage.tsx   ~60 lines

Total: ~25 files, ~1250 lines (vs 1 file, 1170 lines)
Average: ~50 lines per file
Largest: WorkspaceCard.tsx (~80 lines), SessionCard.tsx (~70 lines)
```
