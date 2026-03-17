# UI Audit: Current State vs Research Goals

> Audit conducted 2026-03-16. Maps the current `index.html` against the 3 core actions defined in [ux-research.md](ux-research.md).

## Current Architecture

The UI is a single-page app (vanilla JS, ~975 lines) with 3 hash-routed pages:

| Route | Page | Purpose |
|-------|------|---------|
| `#/` | Workspaces | Grid of workspace cards with health, start form |
| `#/sessions` | Sessions | Running / Pending / Ended panels |
| `#/discover` | Discover | Scan for new workspaces |

Navigation is via pill-style tabs in a sticky top bar.

---

## Audit: Action 1 — LAUNCH

**Goal:** 2 taps from app open to being in the Claude app.

### Current Flow (tap count)

```
Open app
→ See workspace grid (good)
→ Tap "Start Session" button
→ Form expands with Label, Branch, Worktree checkbox (friction!)
→ Tap "Start" button in form
→ App navigates to Sessions page (context switch!)
→ Wait for pending session to resolve
→ Tap URL link when it appears
```

**Current tap count: 4 taps + a page switch + a wait**

### Issues Found

| Issue | Severity | Detail |
|-------|----------|--------|
| **Form before launch** | High | Tapping "Start Session" doesn't start — it opens a form with Label, Branch, and Worktree options. Most launches don't need these. This adds a mandatory decision point and an extra tap. |
| **Page switch on start** | High | After tapping "Start" in the form, `setRoute('/sessions')` forces navigation to the Sessions page. The user loses sight of the workspace they just launched from. They have to orient themselves on a new page. |
| **No progress phases** | High | Pending sessions show a generic yellow spinner + "Waiting for URL..." text. No phase labels (connecting → starting → generating). The user has no sense of progress during the 5-30 second wait. |
| **URL is a small text link** | Medium | When the URL arrives, it renders as a blue text link (`session-link` class). It's small (0.85rem), uses `word-break: break-all`, and blends in with the card. Not the "unmissable payoff moment" we want. |
| **Auto-generated labels are good** | Positive | `randomLabel()` generates fun names like "swift-fix", "bold-patch". These auto-fill when the form opens. |
| **Optimistic UI is good** | Positive | A pending session card is immediately added to state before the API responds. The user sees instant feedback. |

### Gap Summary

- Need: tap workspace card → session starts immediately (no form)
- Need: label/branch/worktree options available but not blocking
- Need: progress phases during wait, not just a spinner
- Need: URL displayed as a large, prominent button when ready
- Need: no page switch — stay in context

---

## Audit: Action 2 — RECONNECT

**Goal:** Open app → running session is right there → 1 tap on URL.

### Current Flow

```
Open app
→ Land on Workspaces page (no running sessions visible!)
→ Tap "Sessions" nav tab
→ Scan Running panel for the right session
→ Tap the small URL text link
```

**Current tap count: 2 taps + visual scanning on a separate page**

### Issues Found

| Issue | Severity | Detail |
|-------|----------|--------|
| **Running sessions not visible on landing** | Critical | The app always opens to the Workspaces page. Running sessions are on a completely separate page. The most likely reason someone reopens the app (30% of opens) requires a tab switch. |
| **No running session summary on workspace cards** | Medium | Workspace cards show "X active" in small meta text, but no URL or quick-reconnect action. You have to go to Sessions to get the URL. |
| **Session identity is weak** | Medium | Session cards show `label || id` as the title, with workspot and branch in meta text. If the user didn't type a label, the ID is a UUID — meaningless. Auto-generated labels help but are random words, not project/branch context. |
| **URL target link is small** | Medium | Same issue as Launch — the URL is a small blue text link, not a big tappable button. |
| **Sessions badge shows count** | Positive | The nav tab shows a badge with active session count. At least you can see something is running from the Workspaces page. |

### Gap Summary

- Need: running sessions visible on the main/landing page, above workspaces
- Need: session URL as a large tappable button, not a text link
- Need: auto-generated identity from workspace + git branch + elapsed time
- Need: no tab switch required to reconnect

---

## Audit: Action 3 — GLANCE

**Goal:** Open app → instant visual signal → green/red for each workspace → zero taps.

### Current Flow

```
Open app
→ See workspace cards with health pills (green/red)
→ See error details on unhealthy workspaces
→ See "X active" count on cards
```

**Current tap count: 0 taps — this mostly works!**

### Issues Found

| Issue | Severity | Detail |
|-------|----------|--------|
| **Health pills work well** | Positive | Green "Ready" / Red "Needs attention" pills with colored dots. Immediately scannable. |
| **Errors shown inline** | Positive | Red error boxes below unhealthy cards show specific issues ("Not authenticated", "Container not running"). No tap needed. |
| **Unhealthy sorted to bottom** | Positive | Healthy workspaces sort first. Good default. |
| **Missing: running session count is subtle** | Low | "2 active" is in small gray meta text. A small badge or number would be more scannable. |
| **Missing: last-checked timestamp** | Low | No indication of when health was last checked. User can't tell if status is fresh or stale. |
| **No cached state on load** | Medium | Shows "Loading..." until API responds. On slow connections or app reopen, there's a blank moment. Should show last-known state from localStorage immediately. |
| **Nav summary is good** | Positive | Top bar shows "3 workspaces · 2 active" — quick aggregate status. |

### Gap Summary

- Mostly good for GLANCE
- Need: more prominent active session indicators on workspace cards
- Need: cached/stale data on app open for instant render
- Nice to have: last-checked timestamps

---

## Audit: State Handling

| State | Current behavior | Issue |
|-------|-----------------|-------|
| **Clean slate** (no sessions, healthy) | Shows workspace grid with "Start Session" buttons | Good |
| **Active sessions** | Hidden on Sessions page | Bad — should be on landing page |
| **Pending** | Yellow spinner + "Waiting for URL..." | Missing phase labels |
| **URL ready** | Small blue text link appears in session card | Should be a large button |
| **Something broken** | Red error boxes on workspace cards | Good |
| **First time** (no workspaces) | "No workspaces yet. Discover environments" link | Okay but could be more helpful |
| **Returning from Claude app** | No `visibilitychange` handler | Stale data until next poll cycle (up to 15s) |

---

## Audit: Technical Details

### What's Good

- **Dark theme, mobile-first CSS** — Clean design with proper CSS variables, 48px min tap targets, responsive grid breakpoints
- **Optimistic UI** — Actions update UI immediately before API response, with rollback on failure
- **Hash routing** — Simple, works for PWA, no page reloads
- **Polling with adaptive frequency** — 3s when pending sessions exist, 15s otherwise
- **Data change detection** — `hashData()` skips re-render if nothing changed
- **Form state preserved during background refresh** — Won't clobber an open start form
- **XSS-safe** — `esc()` function sanitizes all dynamic content

### What Needs Work

| Area | Current | Needed |
|------|---------|--------|
| **Page structure** | 3 separate pages (Workspaces / Sessions / Discover) | 1 main page with running sessions + workspaces + collapsed history |
| **Launch flow** | Form → Start → page switch → wait → small link | Tap card → wait with phases → big "Open in Claude" button |
| **Session URL display** | `<a class="session-link">` small text | Large button-style element, primary color, full width |
| **Progress indicator** | Yellow spinner only | 3-step phase indicator with labels |
| **Return detection** | None | `visibilitychange` listener to refresh data |
| **Cached initial render** | None ("Loading...") | localStorage cache, stale-while-revalidate pattern |
| **Session identity** | Random label or UUID | Auto: `{workspace} / {branch} — {elapsed}` |
| **Service worker** | Basic shell cache (`sw.js`) | Add stale-while-revalidate for API data |

---

## Summary: Priority Changes

### Must Have (core action improvements)

1. **Running sessions on the landing page** — Show active sessions above the workspace grid. No tab switch for RECONNECT.
2. **URL as a big button** — Replace the small text link with a large, styled "Open in Claude" button.
3. **One-tap launch** — Tapping a workspace card starts a session immediately (with auto-generated label). Move label/branch/worktree options to the workspace detail layer.
4. **Progress phases** — Replace the bare spinner with step labels: "Connecting..." → "Starting Claude..." → "Generating URL..."
5. **No page switch on launch** — Stay on the main page. Show the pending/running session inline or at the top of the page.

### Should Have (polish)

6. **`visibilitychange` refresh** — Re-fetch session data when the user returns from the Claude app.
7. **Session auto-identity** — Display `{workspace} / {branch} — {elapsed}` instead of random label or UUID.
8. **Deep-link hint** — Small text under URL: "If it doesn't open directly, check your sessions in the Claude app."
9. **Cached initial render** — Store last API response in localStorage, render immediately on open, refresh async.

### Nice to Have (future)

10. **Consolidated single page** — Merge Sessions and Workspaces into one view with collapsed history section.
11. **Push notifications** — "Your session is ready" when URL arrives while app is backgrounded.
12. **PWA install prompt** — After first successful session, suggest "Add to Home Screen."
13. **Frequency-based workspace ordering** — Most-used workspace shown first/largest.
