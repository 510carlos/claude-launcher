# UI Implementation Plan

> Created 2026-03-16. Based on [ux-research.md](ux-research.md) and [ui-audit.md](ui-audit.md).
>
> **Status: PLANNING — no code changes yet. Backend work in progress by separate agent.**

## Goal

Redesign the frontend to optimize for the 3 core actions: **Launch** (2 taps), **Reconnect** (1 tap), **Glance** (0 taps). Move from a 3-page tab layout to a single adaptive page with detail layers.

## Principles

1. **No new dependencies.** Stay with vanilla JS, no build step.
2. **Single file.** Keep everything in `index.html` (CSS + JS + HTML).
3. **Mobile-first.** Design for 375px width first, scale up.
4. **The app adapts to state.** Running sessions → show them first. Nothing running → workspaces fill the screen. Pending → show progress. Broken → show errors.
5. **Backend API stays the same.** All changes are frontend-only. No new endpoints required (progress phases are client-side estimations based on polling timing).

---

## Phase 1: Core Action Improvements

These changes directly improve the 3 core actions. Do these first.

### 1.1 Running sessions on the landing page

**What:** When there are active sessions (running or pending), show them in a section at the top of the page, above the workspace grid.

**Layout:**
```
┌──────────────────────────────────┐
│  ● ACTIVE (2)                    │
│  ┌──────────────────────────────┐│
│  │ my-project / main    23m    ││
│  │ [████ Open in Claude ████]  ││
│  └──────────────────────────────┘│
│  ┌──────────────────────────────┐│
│  │ api-server / dev      5m    ││
│  │ [████ Open in Claude ████]  ││
│  └──────────────────────────────┘│
└──────────────────────────────────┘
```

**Details:**
- Only show running and pending sessions here. Not stopped/failed.
- Each card shows: workspace name, branch (if available), elapsed time, and the URL as a large button.
- Pending sessions show the progress indicator (see 1.3) instead of the URL button.
- If no active sessions, this section is hidden entirely — workspace grid moves up.
- Tapping the "Open in Claude" button is a direct `<a href>` to the URL.
- Small "Stop" button in the corner of each card for killing.

**Tap count for RECONNECT: 1** (just tap "Open in Claude")

### 1.2 One-tap launch from workspace cards

**What:** Tapping a healthy workspace card immediately starts a session with an auto-generated label. No form, no intermediate step.

**Current:** "Start Session" button → form expands → fill label/branch → tap "Start"
**New:** Tap the workspace card (or a prominent "Launch" button on it) → session starts immediately

**Details:**
- The workspace card itself becomes the launch trigger. Tap anywhere on the card (or the "Launch" button).
- Auto-generates a label via `randomLabel()` (already exists).
- No branch, no worktree by default — just start.
- For users who want options (branch, worktree, custom label): a small "..." or gear icon in the card corner opens a detail layer / bottom sheet with the full form.
- After tapping: the card transitions to show a progress indicator inline, OR the new session appears in the Active section at the top.

**Tap count for LAUNCH: 2** (tap workspace → tap URL when ready)

### 1.3 Progress phases during wait

**What:** Replace the bare yellow spinner with a 3-step progress indicator.

**Phases:**
```
Step 1: Connecting to workspace...     (shown immediately on tap)
Step 2: Starting Claude...             (shown after ~3s or first poll)
Step 3: Generating URL...              (shown after ~8s or second poll)
Done:   ✓ Ready — Open in Claude       (shown when URL is captured)
```

**Implementation:**
- These are **client-side estimations**, not server events. The backend doesn't emit phase events.
- Use `setTimeout` to transition between phases at reasonable intervals (0s → 3s → 8s).
- If the URL arrives before a phase transition, skip straight to "Ready."
- Show a thin progress bar under the steps that creeps forward and jumps at each phase.
- On timeout (>60s): show "Taking longer than usual..." with a retry option.
- On error: show which step failed and why.

**Visual:**
```css
/* Stepper: three dots/labels in a row */
.step { opacity: 0.3; }
.step.active { opacity: 1; }
.step.done { opacity: 1; color: var(--green); }
```

### 1.4 URL as a large button

**What:** Replace the small `<a class="session-link">` with a large, full-width, styled button.

**Current:** `<a class="session-link" href="...">https://claude.ai/code/...</a>` (0.85rem, blue text)

**New:**
```html
<a class="session-url-btn" href="https://claude.ai/code/..." target="_blank">
  Open in Claude
</a>
```

**Styling:**
- Full-width, 56px+ height
- Primary color gradient (blue)
- Bold text, centered
- Border-radius matching the card
- Below it: small muted text "If it doesn't open directly, check your sessions in the Claude app"

### 1.5 No page switch on launch

**What:** Stay on the main page when a session is started. Don't `setRoute('/sessions')`.

**Current:** `startSession()` calls `setRoute('/sessions')` after creating the optimistic pending session.

**New:** Remove the `setRoute('/sessions')` call. Instead:
- Add the pending session to the Active section at the top of the main page.
- Scroll the page to the top so the new pending card is visible.
- The workspace card can show a subtle "Starting..." indicator.

---

## Phase 2: Single Page Consolidation

Merge the 3 pages into 1 adaptive page.

### 2.1 Page layout

```
┌──────────────────────────────────┐
│  Top bar: "Claude Launcher"      │
│  Summary: "3 workspaces · 2 act" │
└──────────────────────────────────┘

┌──────────────────────────────────┐  ← Only if active sessions exist
│  ACTIVE SESSIONS                 │
│  [session cards with URL btns]   │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│  WORKSPACES                      │
│  [workspace card grid]           │
└──────────────────────────────────┘

┌──────────────────────────────────┐  ← Collapsed by default
│  ▼ RECENT (3)                    │
│  [stopped session cards]         │
└──────────────────────────────────┘
```

### 2.2 Remove tab navigation

- Remove the `Workspaces | Sessions | Discover` nav tabs
- Replace with the single adaptive page
- Discovery becomes a button ("Find more workspaces") at the bottom of the workspace grid that opens a sheet/modal

### 2.3 Detail layers

**Workspace detail** (tap a workspace card while holding, or tap "..." icon):
- Full health checks list
- Start with options form (label, branch, worktree)
- Sessions for this workspace
- Could be a slide-up sheet or an expanded card

**Session detail** (tap a session card, not the URL button):
- Full URL (visible and copyable)
- Workspace, branch, label, start time, session ID
- Kill / Delete buttons

### 2.4 Recent sessions section

- Shows stopped/failed sessions, collapsed by default
- Expand to see last N sessions
- "Clear all" button
- Each card has a "Delete" action

---

## Phase 3: Polish

### 3.1 `visibilitychange` refresh

```javascript
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    loadData().then(changed => { if (changed) render(true); });
  }
});
```

Refresh session data whenever the user returns to the app (e.g., after being in the Claude app).

### 3.2 Session auto-identity

Replace random labels as the session card title with context-rich auto-identity:

```
{workspace} / {branch} — {elapsed}
```

Example: `my-project / main — 23m ago`

The random label becomes secondary metadata, not the title.

### 3.3 Cached initial render

```javascript
async function boot() {
  // 1. Render from cache immediately
  const cached = localStorage.getItem('launcher-state');
  if (cached) {
    const data = JSON.parse(cached);
    state.workspaces = data.workspaces;
    state.workspaceHealth = data.health;
    state.sessions = data.sessions;
    render();
  }

  // 2. Fetch fresh data
  try {
    await loadData();
    render();
    // 3. Update cache
    localStorage.setItem('launcher-state', JSON.stringify({
      workspaces: state.workspaces,
      health: state.workspaceHealth,
      sessions: state.sessions,
    }));
  } catch (e) {
    if (!cached) showNotice('Could not load.', 'error');
  }
  scheduleRefresh();
}
```

### 3.4 Improved empty state

For first-time users with no workspaces:

```html
<div class="empty-state">
  <h2>No workspaces configured</h2>
  <p>Add workspace definitions to your <code>.env</code> file:</p>
  <pre>WORKSPOTS='[{"name":"my-project","container":"devcontainer-app-1","dir":"/workspaces/my-project"}]'</pre>
  <p>Then restart the launcher.</p>
  <button onclick="runDiscovery()">Or scan your environment</button>
</div>
```

---

## Phase 4: Future (Not in Scope Now)

- **Push notifications** — "Your session is ready" via Push API + VAPID
- **PWA install prompt** — After first successful session
- **Haptic feedback** — On launch and URL ready moments
- **Frequency-based ordering** — Most-used workspace first
- **Favorites** — Pin workspaces for quick access
- **Keyboard shortcuts** — For desktop use (1-9 to launch workspace N)

---

## Dependencies

- **No backend changes required for Phase 1-2.** All changes are frontend-only.
- **Phase 3.2 (auto-identity)** benefits from the backend returning git branch info in session records. Check if this is already available in the session API response.
- **Backend agent work in progress** — do not edit backend files. Frontend changes are safe.

## Files to Modify

| File | Changes |
|------|---------|
| `app/static/index.html` | All UI changes (HTML structure, CSS, JS) |
| `app/static/sw.js` | May need updates for API caching strategy |
| `app/static/manifest.json` | No changes expected |

## Execution Order

1. Phase 1 first (core action improvements) — biggest impact, lowest risk
2. Phase 2 second (single page consolidation) — structural change, depends on Phase 1
3. Phase 3 third (polish) — refinements on top of new structure
4. Phase 4 — future work, not planned now
