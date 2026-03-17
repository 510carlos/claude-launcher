# Frontend Architecture Plan

> Research conducted 2026-03-16. Covers tooling, framework selection, component architecture, and migration strategy.

## Decision: Bun + Vite + Preact + Signals

### Tooling: Bun + Vite (not Bun alone)

**Bun** as package manager and runtime (fast installs, fast script execution). **Vite 8** (with Rolldown) as the build tool.

Why not Bun's bundler alone:
- No API proxy (we need to proxy `/api/*` to FastAPI on :8765 during dev)
- No PWA plugin (Vite has `vite-plugin-pwa` for service worker generation, precaching, install prompts)
- HMR is incomplete (missing APIs, `prune()` callbacks never fire)
- Plugin ecosystem is thin (Bun has a handful, Vite has 800+)
- Vite 8 + Rolldown closed the speed gap (~0.4s cold builds vs Bun's ~0.8s)

What we get:
- `bun install` — 9-30x faster than npm
- `bun run dev` — runs Vite dev server with HMR, proxy, and React Fast Refresh
- `bun run build` — Vite production build with tree-shaking, minification, code splitting

### Framework: Preact + Signals

| Criterion | Preact + Signals | Runner-up: Svelte 5 |
|-----------|-----------------|---------------------|
| **Bundle (gzipped)** | ~5-7 KB framework | ~4-6 KB runtime |
| **Total shipped** | ~12-18 KB | ~10-16 KB |
| **TypeScript** | Excellent (full .tsx) | Good (some TS features unsupported in .svelte) |
| **State management** | Signals — `signal([])`, auto-rerenders | Runes — `$state()`, `$derived()` |
| **Learning curve** | Very low (it IS React's API) | Low-moderate (new template syntax) |
| **Migration cost** | Low — innerHTML → JSX is nearly mechanical | Moderate — new file format, template syntax |
| **Ecosystem** | Strong (React-compatible ecosystem) | Strong (SvelteKit, but non-portable knowledge) |
| **Production validation** | Shopify mandated Preact for all UI extensions (64 KB budget) | Widely used, Rich Harris at Vercel |

**Why Preact + Signals wins for this app:**

1. **Right-sized.** 5-7 KB for a real component model and reactivity. Purpose-built for mobile PWAs where bundle size matters.

2. **Signals map perfectly to current architecture.** Our `state` object with `workspaces`, `sessions`, `workspaceHealth` arrays → 3-4 signals. Components reading a signal auto-rerender when it changes. No context providers, no reducers, no boilerplate.

3. **Lowest migration cost.** `${esc(ws.name)}` → `{ws.name}` (JSX auto-escapes). `onclick="quickLaunch('${esc(ws.name)}')"` → `onClick={() => quickLaunch(ws.name)}`. Nearly mechanical conversion.

4. **No mental model traps.** Unlike SolidJS (where React habits cause subtle bugs because components run once), Preact genuinely IS React's API. React knowledge transfers 1:1.

5. **Polling + optimistic UI is trivial.** Polling loop updates signals, only affected components rerender. Optimistic updates: mutate signal → UI updates instantly → fetch in background → update signal again.

**What we rejected:**
- **Vue 3** — 50 KB gzipped baseline. 10x heavier than Preact. Unjustifiable for this app.
- **SolidJS** — "Looks like React but isn't React" problem. Can't destructure props, conditional rendering works differently. Higher learning curve for subtle reasons.
- **Lit** — Web components are great for libraries, not apps. Shared state story is weak. Class-based API is verbose.
- **Vanilla TS** — 0 KB overhead but you maintain your own component system and reactivity. Short-term gain, long-term maintenance liability.

---

## Component Architecture

### Component Breakdown (13 components + 2 pages)

**Pages (2):**
| Component | Purpose |
|-----------|---------|
| `DashboardPage` | Main view: active sessions + workspace grid + recent sessions |
| `DiscoveryPage` | Scan results with compatibility categories |

**Section Components (5):**
| Component | Purpose |
|-----------|---------|
| `TopBar` | Brand, summary text, discover button |
| `NoticeToast` | Info/error toast messages |
| `ActiveSessions` | Running/pending session cards at top |
| `WorkspaceGrid` | Grid of workspace cards |
| `RecentSessions` | Collapsible ended session list |

**Card Components (3):**
| Component | Purpose |
|-----------|---------|
| `SessionCard` | Active or ended session (conditional rendering) |
| `WorkspaceCard` | Workspace with health, launch, options form |
| `DiscoveryCard` | Scan result with compatibility status |

**Leaf Components (3):**
| Component | Purpose |
|-----------|---------|
| `ProgressSteps` | 3-phase progress indicator with bar |
| `HealthPill` | Status dot/pill (Ready, Needs attention, Unknown) |
| `OptionsForm` | Inline form for label, branch, worktree |

### File Tree

```
app/
├── static/
│   ├── manifest.json
│   ├── sw.js                    # Service worker (kept simple, manual)
│   ├── icon-192.png
│   └── icon-512.png
│
├── frontend/                    # NEW: Vite + Preact project
│   ├── index.html               # Shell: <div id="app">, <script type="module">
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts           # Proxy /api → FastAPI, PWA plugin
│   │
│   └── src/
│       ├── main.tsx             # Mount <App />, register SW, boot
│       ├── app.tsx              # Router, layout, NoticeToast
│       ├── app.css              # Global styles (CSS variables, reset, base)
│       │
│       ├── state/
│       │   ├── signals.ts       # workspaces, sessions, health, notices signals
│       │   └── polling.ts       # Poll loop: refresh signals on interval
│       │
│       ├── api/
│       │   ├── client.ts        # Base fetch wrapper with error handling
│       │   ├── sessions.ts      # start, kill, delete, list, output
│       │   ├── workspaces.ts    # list, health, fix, recheck, remove
│       │   └── discovery.ts     # scan, add workspot
│       │
│       ├── components/
│       │   ├── TopBar.tsx
│       │   ├── NoticeToast.tsx
│       │   ├── ActiveSessions.tsx
│       │   ├── SessionCard.tsx
│       │   ├── WorkspaceGrid.tsx
│       │   ├── WorkspaceCard.tsx
│       │   ├── RecentSessions.tsx
│       │   ├── DiscoveryCard.tsx
│       │   ├── ProgressSteps.tsx
│       │   ├── HealthPill.tsx
│       │   └── OptionsForm.tsx
│       │
│       ├── pages/
│       │   ├── DashboardPage.tsx
│       │   └── DiscoveryPage.tsx
│       │
│       ├── types.ts             # Mirrors app/models.py — keep in sync
│       └── utils.ts             # fmtTime, randomLabel, randomBranch
│
├── Dockerfile                   # Updated: build frontend, serve via FastAPI
├── main.py
├── models.py
├── ...
```

### Vite Config

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

export default defineConfig({
  plugins: [preact()],
  server: {
    proxy: {
      '/api': 'http://localhost:8765',
      '/status': 'http://localhost:8765',
    },
  },
  build: {
    outDir: '../static/dist',   // Build output served by FastAPI
    emptyOutDir: true,
  },
});
```

---

## State Management: Preact Signals

```typescript
// state/signals.ts
import { signal, computed } from '@preact/signals';
import type { Workspace, Session, HealthStatus } from '../types';

// Core state
export const workspaces = signal<Workspace[]>([]);
export const sessions = signal<Session[]>([]);
export const health = signal<HealthStatus[]>([]);

// Derived
export const activeSessions = computed(() =>
  sessions.value.filter(s => s.status === 'running' || s.status === 'pending')
);
export const endedSessions = computed(() =>
  sessions.value.filter(s => s.status === 'stopped' || s.status === 'failed')
);

// UI state
export const notices = signal<{ msg: string; kind: 'info' | 'error' }[]>([]);
export const route = signal<'/' | '/discover'>('/');
```

Components just read signals — no props drilling for global state:

```tsx
// components/ActiveSessions.tsx
import { activeSessions } from '../state/signals';
import { SessionCard } from './SessionCard';

export function ActiveSessions() {
  const active = activeSessions.value;
  if (!active.length) return null;

  return (
    <section>
      <h2>Active Sessions ({active.length})</h2>
      {active.map(s => <SessionCard key={s.id} session={s} />)}
    </section>
  );
}
```

---

## CSS Strategy

Keep the current CSS variables and dark theme. Move from one big `<style>` block to organized CSS files:

| File | Contents |
|------|----------|
| `app.css` | CSS variables, reset, body, layout utilities |
| Component-scoped via CSS modules or class prefixes | Each component's styles |

For this app's scale, **plain CSS with BEM-lite naming** is fine. No Tailwind (adds build complexity), no CSS-in-JS (runtime overhead). The existing CSS variables are already well-organized.

---

## Type Sync: Manual with Convention

```typescript
// types.ts — Mirrors app/models.py — keep in sync
export interface Workspace {
  name: string;
  runtime: 'docker' | 'host';
  dir: string;
  container: string | null;
  claude_bin: string;
  server_capacity: number;
  source: 'env' | 'file';
}

export interface Session {
  id: string;
  workspot: string;
  label: string;
  branch: string | null;
  url: string | null;
  status: 'pending' | 'running' | 'stopped' | 'failed';
  created_at: string;
}

export interface HealthStatus {
  workspot: string;
  runtime_ok: boolean;
  repo_exists: boolean;
  git_ok: boolean;
  claude_bin_ok: boolean;
  auth_ok: boolean;
  issues: string[];
}
```

Convention: when you change a Pydantic model, update `types.ts` in the same commit.

---

## Migration Strategy

### Phase 0: Setup (no UI changes)
1. `mkdir app/frontend && cd app/frontend`
2. `bun init` + `bun add preact @preact/signals vite @preact/preset-vite`
3. Set up `vite.config.ts` with API proxy
4. Create `index.html` shell, `src/main.tsx` that renders "Hello"
5. Verify: `bun run dev` → Preact app loads, `/api/*` proxied to FastAPI

### Phase 1: Extract non-UI code
1. Create `types.ts` — copy interfaces from Python models
2. Create `api/client.ts` + `api/sessions.ts` + `api/workspaces.ts` — move all fetch calls
3. Create `state/signals.ts` — replace global state object
4. Create `state/polling.ts` — connect API to signals
5. Create `utils.ts` — move `fmtTime`, `randomLabel`, `esc` (though JSX auto-escapes)

### Phase 2: Build components bottom-up
1. `HealthPill.tsx` — stateless, easy to test
2. `ProgressSteps.tsx` — self-contained state machine
3. `SessionCard.tsx` — reads from session prop
4. `WorkspaceCard.tsx` — reads from workspace prop + health signal
5. `OptionsForm.tsx` — local form state
6. `ActiveSessions.tsx` — composes SessionCard
7. `WorkspaceGrid.tsx` — composes WorkspaceCard
8. `RecentSessions.tsx` — collapsible + composes SessionCard
9. `TopBar.tsx`, `NoticeToast.tsx`

### Phase 3: Assemble pages
1. `DashboardPage.tsx` — composes ActiveSessions + WorkspaceGrid + RecentSessions
2. `DiscoveryPage.tsx` — migrate discovery rendering
3. `app.tsx` — router + layout + TopBar + NoticeToast
4. `main.tsx` — mount, register SW, start polling

### Phase 4: Build integration
1. Update `vite.config.ts` build output → `../static/dist/`
2. Update `Dockerfile` to run `bun run build` during image build
3. Update FastAPI to serve from `static/dist/` (or keep serving `static/` and put built assets there)
4. Remove old `index.html`
5. Verify production build works in Docker

### Phase 5: Polish
1. Add `vite-plugin-pwa` for proper service worker generation
2. Add localStorage caching in signals (persist/restore on mount)
3. Add `visibilitychange` handler in polling module
4. CSS cleanup — organize into files, remove unused styles

---

## Build & Serve in Production

```dockerfile
# In Dockerfile — add build step
FROM oven/bun:1.3 AS frontend
WORKDIR /build
COPY app/frontend/ .
RUN bun install --frozen-lockfile && bun run build

FROM python:3.12-slim
# ... existing setup ...
COPY --from=frontend /build/dist/ /app/static/dist/
```

FastAPI serves the built frontend from `static/dist/`. The API proxy is only needed in dev (Vite dev server). In production, everything is same-origin.

---

## What We Gain

| Before | After |
|--------|-------|
| 1 file, 1100+ lines | 20+ files, ~50-100 lines each |
| innerHTML with manual `esc()` | JSX with automatic escaping |
| Global `state` object, manual `render()` calls | Signals — components auto-rerender |
| No types | Full TypeScript with interfaces mirroring Python models |
| No build step (pro and con) | Vite build with tree-shaking, minification, code splitting |
| ~0 KB framework overhead | ~5-7 KB Preact + Signals (gzipped) |
| Works but hard to modify | Easy to add features, refactor, and debug |

## What We Keep

- Same dark theme, same CSS variables, same visual design
- Same API endpoints, same data flow
- Same PWA behavior (manifest, icons, installable)
- Same polling pattern, same optimistic UI approach
- Bun as runtime aligns with existing Docker/containerized deployment
