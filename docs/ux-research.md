# UX Research: Claude Launcher Core User Experience

> Research conducted 2026-03-16. Covers user context, core actions, competitive landscape, mobile UX patterns, and deep-dive analysis on hard problems.

## Table of Contents

- [User Context](#user-context)
- [Competitive Landscape](#competitive-landscape)
- [The 3 Core Actions](#the-3-core-actions)
  - [Action 1: Launch](#action-1-launch--connect-claude-to-this-project)
  - [Action 2: Reconnect](#action-2-reconnect--get-back-to-my-running-session)
  - [Action 3: Glance](#action-3-glance--is-everything-okay)
- [Action Priority](#action-priority)
- [North Star](#north-star)
- [Page Structure](#page-structure)
- [Deep Dive: App State Machine](#deep-dive-app-state-machine)
- [Deep Dive: Hard Problems](#deep-dive-hard-problems)
- [Deep Dive: The Launch Wait](#deep-dive-the-launch-wait)
- [Deep Dive: PWA Technical Considerations](#deep-dive-pwa-technical-considerations)
- [Mobile UX Patterns](#mobile-ux-patterns)

---

## User Context

The user is a developer. They are **not at their desk**. They're on the couch, in bed, on a break, commuting. They pull out their phone because they want Claude working on their code. That's it. They don't want to SSH into anything. They don't want to type commands. They want to go from "idea" to "Claude is working on it" as fast as possible.

This app is a **TV remote**. You don't stare at the remote — you use it to get to what you actually want: the Claude app, connected to your codebase.

---

## Competitive Landscape

### Key Finding: Claude Launcher Is Unique

We analyzed 14 projects in the Claude Code tooling space. **None of them do what Claude Launcher does.** Every other project falls into one of these categories:

| Approach | Projects |
|----------|----------|
| **Builds its own chat UI** | CloudCLI, claude-code-web (vultuk), claude-code-webui (sugyan), claude-code-web-ui (lennardv2), Claudia, CodePilot, claude-code-by-agents |
| **Streams the CLI terminal via xterm.js** | Codeman, 247-claude-code-remote |
| **TUI session manager (native CLI)** | CCManager, Agent of Empires, claude-session-manager |
| **Other** | claude-code-desktop-remote (controls Desktop app via CDP), JessyTsui/Claude-Code-Remote (notification relay via email/Telegram) |

**Zero** projects use `claude remote-control` to generate a URL and hand it to the user so they use the actual Claude phone app / claude.ai interface.

### What This Means

Claude Launcher is a **session orchestrator**, not a chat client. It solves one problem: getting a `claude remote-control` URL from the right environment to your phone, fast. The user then interacts through the real Claude app, getting all of Claude's features (tool use, artifacts, conversation history, mobile notifications) without re-implementation.

### Detailed Project Breakdown

| # | Project | What It Actually Does |
|---|---------|----------------------|
| 1 | [CloudCLI / claudecodeui](https://github.com/siteboon/claudecodeui) | Full web IDE — file explorer, Git integration, MCP management. Auto-discovers sessions from `~/.claude`. Desktop + mobile |
| 2 | [claude-code-web (vultuk)](https://github.com/vultuk/claude-code-web) | xterm.js terminal emulator wrapping Claude CLI via node-pty + WebSocket. Own session management |
| 3 | [claude-code-webui (sugyan)](https://github.com/sugyan/claude-code-webui) | React/TypeScript chat UI. Runs CLI as subprocess, streams responses in custom interface |
| 4 | [claude-code-web-ui (lennardv2)](https://github.com/lennardv2/claude-code-web-ui) | Nuxt 4 chat UI. Voice input, TTS, drag-and-drop images. Alpha stage |
| 5 | [Codeman](https://github.com/Ark0N/Codeman) | tmux session manager + xterm.js web dashboard. Streams real CLI output, not a chat replacement |
| 6 | [Claudia / opcode](https://github.com/getAsterisk/claudia) | YC-backed Tauri desktop GUI. Session checkpointing, branching, visual timeline. Parses `--output-format stream-json` |
| 7 | [CodePilot](https://github.com/op7418/CodePilot) | Electron + Next.js desktop app. SQLite storage, multi-provider, session checkpoints |
| 8 | [CCManager](https://github.com/kbwo/ccmanager) | Rust TUI, ~811 stars. Supports 8+ AI CLIs (Claude, Gemini, Codex, Cursor, Copilot, etc.). Git worktree integration |
| 9 | [Agent of Empires](https://github.com/njbrake/agent-of-empires) | Rust TUI over tmux. Docker sandboxing, git worktrees. Supports 8+ AI CLIs |
| 10 | [claude-session-manager](https://github.com/Swarek/claude-session-manager) | Shell utility. `cx` command for organizing multiple terminal sessions. No UI |
| 11 | [247-claude-code-remote](https://github.com/QuivrHQ/247-claude-code-remote) | xterm.js + node-pty + tmux remote terminal. Next.js dashboard. Tailscale + Fly.io |
| 12 | [claude-code-desktop-remote](https://github.com/HLE-C0DE/claude-code-desktop-remote) | Remote control of Claude Desktop (Electron app) via Chrome DevTools Protocol. Windows only |
| 13 | [Claude-Code-Remote (JessyTsui)](https://github.com/JessyTsui/Claude-Code-Remote) | Notification relay via Email, Telegram, LINE, Desktop. Hook-based command injection |
| 14 | [claude-code-by-agents](https://github.com/baryhuang/claude-code-by-agents) | Multi-agent orchestration with custom React chat UI. @mention routing between agents |

---

## The 3 Core Actions

Every interaction with Claude Launcher is one of these three moments.

### Action 1: LAUNCH — "Connect Claude to this project"

**The moment:** You have a task in mind. You know which project. You want Claude on it, now.

**The ideal flow:**
```
Open app → tap workspace → wait a few seconds → tap URL → you're in the Claude app
```

**What "smooth" means here:**

- **Recognize, don't recall.** Workspaces should be instantly recognizable by name and color. The most-used workspace should jump out. Don't make the user scan a list.
- **Minimum taps.** The ideal is 2 taps: tap workspace, tap URL. Every additional step (label form, branch input, confirmation dialog) is friction.
- **The wait is the hardest part.** The 5-30 seconds while `remote-control` starts is where users feel friction. A bare spinner kills confidence. Show phase labels: "Connecting to container..." → "Starting Claude..." → "Generating URL..." Each transition resets the patience clock.
- **The URL moment.** When the URL appears, it should be unmissable. Big, tappable, maybe auto-opens. The primary action shifts from "Launch" to "Open in Claude." This is the payoff — make it feel like a reward.

**Edge cases:**

- Auth expired → tell the user immediately, before they try to launch. Don't waste 30 seconds.
- Container down → same, show up front so no tap is wasted.
- User always uses the same workspace → the app should know. Put the most-used one front and center.

---

### Action 2: RECONNECT — "Get back to my running session"

**The moment:** You started a session 20 minutes ago. You switched apps or the phone slept. Now you want to continue.

**The ideal flow:**
```
Open app → running session is right there → tap URL → you're back in the Claude app
```

**What "smooth" means here:**

- **Running sessions should be the first thing you see.** If there's an active session, that's almost certainly why the user is opening the app. Don't make them switch to a Sessions tab. Put it at the top, above workspaces.
- **One tap.** The URL should be a giant tappable area. The user is probably one-handing their phone. Don't make them aim for a small link.
- **Know which is which.** With 2-3 running sessions, they need to be distinguishable at a glance: project name, branch, time since start. `my-project / main / 23m ago` is enough.
- **Don't show stopped sessions here.** The reconnect flow is about what's alive right now. Dead sessions are for cleanup, not this moment.

**Edge cases:**

- Session died while the user was away → don't show a dead URL. Show it stopped and offer to start a new one with one tap.
- No running sessions → get out of the way, show workspaces so the user can launch.

---

### Action 3: GLANCE — "Is everything okay?"

**The moment:** You open the app not to do anything, just to check. Are my environments healthy? Is anything running?

**The ideal flow:**
```
Open app → instant visual signal → green means good, red means trouble → done (zero taps)
```

**What "smooth" means here:**

- **Zero taps to get the answer.** The moment the app loads, green/red/amber for every workspace. Status should come from cache and update in the background.
- **Running session count per workspace.** A small badge: "2 running" next to a workspace name tells everything.
- **If something's wrong, tell me what.** A red dot is useless without context. "Auth expired" or "Container stopped" in plain text, on the card. No tap into a details view needed.
- **Timestamp.** "Checked 30s ago" or "Last session: 2h ago" gives confidence the status is fresh.

**Edge cases:**

- Everything green, nothing running → "clean slate" state. Should feel inviting, not empty. Launch action should be prominent.
- Everything red → don't overwhelm. Prioritize — tell the user the one thing they can fix first.

---

## Action Priority

These aren't equal. In terms of frequency and impact:

```
LAUNCH      ████████████████████  (60% of opens — this is why the app exists)
RECONNECT   ████████████          (30% of opens — coming back to active work)
GLANCE      ████                  (10% of opens — checking in)
```

**Launch** is the app. If launch isn't buttery smooth, nothing else matters. **Reconnect** is what makes it sticky — if coming back is effortless, people keep using it. **Glance** is what builds trust — if you can always tell the state of things, you feel in control.

---

## North Star

> Open the app. See what's running. Tap once. Be in Claude.

At most **2 taps** from app open to being inside the Claude app, connected to your code. Everything else — labels, branches, worktrees, history, settings — is secondary and should never be in the way of those 2 taps.

---

## Page Structure

### Recommendation: 1 Page + Detail Layers

The current 2-page design (Workspaces tab / Sessions tab) splits by data model. But the user thinks in actions, not entities. All 3 core actions happen in the **same moment** — when you first open the app. Splitting them across pages means one always requires an extra tap.

**One main page that adapts to the user's state:**

```
┌──────────────────────────────────┐
│  ACTIVE SESSIONS (if any)        │  ← RECONNECT (30%)
│  ┌──────────────────────────────┐│
│  │ my-project / main  23m ago  ││
│  │ [████ Open in Claude ████]  ││
│  └──────────────────────────────┘│
│                                  │
│  WORKSPACES                      │  ← LAUNCH (60%) + GLANCE (10%)
│  ┌────────────┐ ┌──────────────┐│
│  │ my-project │ │ api-server   ││
│  │ 🟢 Ready   │ │ 🟢 Ready     ││
│  │ [Launch]   │ │ [Launch]     ││
│  └────────────┘ └──────────────┘│
│  ┌────────────┐                  │
│  │ staging    │                  │
│  │ 🔴 Auth    │                  │
│  └────────────┘                  │
│                                  │
│  ──── Recent ────                │  ← Collapsed
│  stopped session 1    2h ago     │
│  stopped session 2    5h ago     │
└──────────────────────────────────┘
```

**Tap comparison:**

| Action | Current (2 pages) | Proposed (1 page) |
|--------|-------------------|-------------------|
| RECONNECT | Open → Sessions tab → find → tap URL = **3 taps** | Open → tap URL = **1 tap** |
| LAUNCH | Open → find card → Start → tap URL = **3 taps** | Open → tap Launch → tap URL = **2 taps** |
| GLANCE | Open → see health = **0 taps** | Open → see health + sessions = **0 taps** |

**Detail layers (not pages):**

| Layer | Purpose | Access |
|-------|---------|--------|
| **Workspace detail** | Full health breakdown, start with options (label/branch/worktree), workspace session history | Tap a workspace card |
| **Session detail** | URL (big, tappable), metadata, kill/delete actions | Tap a session card |
| **Discovery** (sheet) | Scan and add new workspaces | Button at bottom of workspace list |

Everything 90% of the time → one screen, no scrolling on phone. The other 10% → one tap deeper, never two.

---

## Deep Dive: App State Machine

*(Iteration 1 — thinking about the app as states, not pages)*

The app should adapt its layout to the user's state, not show a static page structure.

### All Possible States When Opening the App

| State | What's happening | User intent | What they should see |
|-------|-----------------|-------------|---------------------|
| **Clean slate** | No sessions running, workspaces healthy | LAUNCH | Workspaces front and center, ready to tap |
| **Active sessions** | 1+ sessions running | RECONNECT | Running session URLs at top, big and tappable |
| **Pending** | Just tapped Launch, waiting for URL | WAIT | Progress phases with step labels |
| **URL ready** | URL just arrived | OPEN IT | Giant "Open in Claude" button, auto-copy |
| **Something broken** | Workspace unhealthy | DIAGNOSE | What's wrong in plain text, on the card |
| **First time** | No workspaces configured | SET UP | Friendly empty state with `.env` instructions |
| **Returning** | Was in Claude app, came back | VARIES | Refreshed state, current sessions visible |

### State Transitions

```
                    ┌─────────┐
          ┌────────►│  CLEAN  │◄──────────┐
          │         │  SLATE  │           │
          │         └────┬────┘           │
          │              │ tap Launch     │ kill session
          │              ▼                │
          │         ┌─────────┐           │
          │         │ PENDING │──timeout──► ERROR
          │         └────┬────┘           │
          │              │ URL arrives    │
          │              ▼                │
          │         ┌─────────┐           │
          │         │  READY  │           │
          │         └────┬────┘           │
          │              │ tap URL        │
          │              ▼                │
          │         ┌─────────┐           │
          └─────────│IN CLAUDE│───────────┘
           come back│  APP    │
                    └─────────┘
```

### Emotional Arc

- **Clean Slate** → calm, ready, inviting
- **Pending** → anxious ("is it working?") — **needs the most design attention**
- **Ready** → reward ("it worked!") — **the payoff moment, make it feel good**
- **In Claude App** → focused on work (launcher forgotten)
- **Returning** → needs instant re-orientation

**Key insight:** The Pending → Ready transition is where you either delight or lose the user. A bare spinner during Pending kills confidence. A big animated payoff at Ready creates positive association.

---

## Deep Dive: Hard Problems

*(Iteration 2 — the gaps that aren't obvious until you trace the full flow)*

### Hard Problem 1: The URL Handoff — Simpler Than Expected

**Severity: Low — it just works.**

The `claude.ai/code/...` URL is a universal/app link. When the user taps it on their phone:
- **iOS:** The Claude app opens (universal link intercept)
- **Android:** The Claude app opens (app link intercept)

No share sheets, no clipboard workarounds, no in-app browser worries. The native app claim on `claude.ai` URLs handles the routing. Tap the link → Claude app opens → session is there.

**The only nuance:** The app may not deep-link directly *into* the session — the user might land on the Claude home screen and need to navigate to their sessions list. But the session is always there. See [Hard Problem 2](#hard-problem-2-url-deep-link-isnt-perfect) for the mitigation hint.

**Implementation:** A simple `<a href>` link or `window.location.href` is all that's needed. No platform detection, no special handling. Optionally offer "Copy URL" as a secondary action for power users who want to paste it somewhere else.

### Hard Problem 2: URL Deep-Link Isn't Perfect

**Severity: Low — works, just needs a hint.**

When the user taps the generated `claude.ai/code/...` URL, it opens the Claude app/site but **doesn't always land directly in the session**. The user may need to navigate to their sessions or workspaces list within the Claude app to find the new session. This is Anthropic's deep-link behavior, not something we control.

**Observed behavior:**
- URL opens claude.ai successfully
- Session IS created and available
- But the user may land on the Claude home screen, not inside the session
- Going to the sessions/workspaces view in Claude shows it there

**No complaints so far** — it works, just requires one extra navigation step sometimes.

**Mitigation in our UI:** Show a brief, friendly hint below the URL when it appears:

```
┌──────────────────────────────────┐
│ ✓ Session ready                  │
│                                  │
│ [████ Open in Claude ████]       │
│                                  │
│ If it doesn't open directly,     │
│ check your sessions in the       │
│ Claude app.                      │
└──────────────────────────────────┘
```

This sets the right expectation without alarming the user. Two lines, only shown alongside the URL — not a warning, just a gentle tip. Experienced users will stop reading it after the first time.

### Hard Problem 3: Session Identity

With 2-3 running sessions, how do you tell them apart? Labels are optional and phone users won't type them.

**Solution: auto-generate from what we already know.**

The launcher already runs git commands (for worktree sessions) and knows the workspace name and start time. Combine these into an automatic identity:

```
my-project / main           23m ago
api-server / feature-auth    5m ago
staging / hotfix-login       1h ago
```

Format: `{workspace} / {branch} — {elapsed time}`

Labels become optional extra context on top of auto-generated identity, not a requirement for telling sessions apart.

### Hard Problem 3: Information Density on Phone

One page with 5 workspaces + 2 running sessions = 7 cards. On a phone, that's scrolling.

**Layout rules:**
- Running sessions always at top (most likely target)
- If > 2 running sessions: horizontal scroll, not vertical stack
- Workspace cards: compact 2-column grid (name + health dot + launch button)
- Recent/stopped sessions: collapsed by default, below the fold
- If > 6 workspaces: consider a "favorites" pin or frequency-based ordering

**Goal:** Everything the user needs 90% of the time visible without scrolling on a standard phone screen (375px width, ~667px viewport).

### Hard Problem 4: Post-Handoff Return

After the user taps the URL and goes to the Claude app, the launcher's job is done. When they return:

```javascript
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    refreshAllSessions(); // Re-fetch from API
  }
});
```

- Refresh all session statuses (some may have stopped while away)
- Replace any stale "just launched" progress UI with the current session card
- Running sessions still show their URL for easy re-open
- Don't auto-navigate — user chose to come back, show current state

### Hard Problem 5: The "First Time" Empty State

No workspaces configured → the app is useless. But this is the first impression.

**Don't show:** a blank page, an error, or a loading spinner that resolves to nothing.

**Do show:**
- Clear headline: "No workspaces configured yet"
- One-sentence explanation of what workspaces are
- Copyable `.env` example snippet
- If auto-discovery is available: "Or scan your environment" button
- An example workspace card (greyed out) so the user understands the UI shape

---

## Deep Dive: The Launch Wait

*(Deep research on the 5-30 second wait — the make-or-break moment)*

### Psychology of Wait Times

| Time | User perception | Required feedback |
|------|----------------|-------------------|
| 0-3s | "System is responding" | Basic indicator sufficient |
| 3-10s | "I'm not in direct control" | Must show what's happening |
| 8-12s | **Anxiety spike** if only a spinner | Phase labels buy more time |
| 15-20s | Assumes failure without new info | Step counter or allow backgrounding |
| 30s+ | Assumes broken unless explicitly told | Hard timeout with actionable error |

Source: Nielsen (1993), revalidated by Google (2017) for mobile.

### Recommended: 3-Step Progress with Creeping Bar

```
Phase 1: Connecting to workspace...    [████░░░░░░░░]  ~33%
Phase 2: Starting Claude...            [████████░░░░]  ~66%
Phase 3: Generating URL...             [██████████░░]  ~90%
Done:    ✓ Ready                       [████████████]  100%
```

**Implementation details:**
- Each phase transition resets the patience clock — user mentally experiences three short waits, not one long wait
- Progress bar should **accelerate** (slow start, fast finish) — research shows this is perceived as faster (Harrison et al., CHI 2007)
- Between known phases, bar creeps forward slowly (never reaches next detent) to signal "still working"
- Show estimated time: "Usually takes 10-20 seconds"
- Cancel button always visible — feeling of control reduces anxiety

### Allow Backgrounding

If the user switches apps during the wait:
- Operation continues server-side
- Workspace card on main page shows inline "Starting..." with small spinner
- When URL is ready: push notification "Your session is ready — tap to open"
- On return to app: show completed session card with URL

### The Payoff Moment (URL Ready)

1. Stepper shows final checkmark with brief animation
2. 200ms pause — let completion register
3. "Open in Claude" button animates in (scale-up + fade, not slide — scale feels like "it materialized")
4. Auto-copy URL to clipboard + toast: "URL copied"
5. Optional: haptic feedback (single medium tap)
6. If backgrounded: push notification with URL

### Failure States

**Phase-specific errors are critical.** Don't show generic "Something went wrong."

```
  [✓] Connecting to workspace
  [✗] Starting Claude — Failed
      Container "devcontainer-app-1" is not running.

      [Try Again]    [View Details]
```

- Hard timeout at 60 seconds client-side (independent of server)
- Retry should restart from the failed phase, not from scratch
- "View Details" for power users — show raw error messages (this is a dev tool)

---

## Deep Dive: PWA Technical Considerations

### App Shell Caching Strategy

| Content | Cache Strategy | Why |
|---------|---------------|-----|
| HTML, CSS, JS, fonts, icons | **Cache-First (Precache)** | Never changes between deploys; revisioned URLs |
| API: workspace list | **Stale-While-Revalidate** | Show cached data instantly, refresh in background |
| API: session status | **Network-First** (3s timeout) | Status is time-sensitive; fall back to cache if offline |

This means:
- App shell loads instantly from cache on every open (even offline)
- Workspace list shows last-known data immediately, refreshes async
- Session status always tries network first (stale status = bad UX for this data)

### Push Notifications

| Platform | Supported? | Notes |
|----------|-----------|-------|
| Chrome/Edge (Android) | Yes | Works from browser tab |
| Chrome/Edge (Desktop) | Yes | Works from browser tab |
| Safari (macOS 16.1+) | Yes | Standard Web Push |
| Safari (iOS 16.4+) | **Only if installed to Home Screen** | Must be added via "Add to Home Screen" in Safari |
| Chrome on iOS | No | Must use Safari on iOS |

**Implementation:** VAPID keys + Push API on server side. Service worker handles `push` event, shows notification. On `notificationclick`, open/focus the app.

**For iOS:** The install-to-home-screen requirement means we should prompt installation **before** offering notification permission. Tie the install prompt to a feature: "Install to get notified when your session is ready."

### Install Prompt Timing

- **Never on first page load.** User hasn't seen value yet.
- **After first successful session launch.** This is the "conversion moment" — they've seen the value.
- **Non-intrusive.** Snackbar for 4-7 seconds, or persistent option in settings area.
- **iOS:** Safari doesn't support `beforeinstallprompt`. Show manual instructions: "Tap Share → Add to Home Screen."

### Offline Behavior

The app can't launch sessions without its backend. But the shell should still load.

1. App shell loads from cache (instant, even offline)
2. API calls fail → show cached workspace data with banner: "Offline — showing last known state"
3. Disable action buttons (Launch, Stop) with tooltip: "Unavailable while offline"
4. If no cached data (first visit while offline): "Can't reach the server. Check your connection." + Retry button

---

## Mobile UX Patterns

Research into mobile-first UX patterns for quick-action apps (smart home controllers, deployment dashboards, server monitoring).

### The "Giant Button" Pattern

When your app does one thing, make that one thing unmissable.

- **Minimum 44x44px touch targets** (Apple HIG), but for the primary action go 120px+ diameter
- Primary action should be 3-5x larger than any secondary element
- Layout: status at top (passive), primary action in the middle (giant), secondary actions at bottom (small)

**The Smart Home "Scene" analogy:** Apps like Apple Home use "scene" buttons — large cards that trigger complex multi-step operations with a single tap. Claude Launcher's "launch" action is exactly this.

### Status-at-a-Glance

Status pages (Atlassian Statuspage, Better Stack) have converged on a universal language:

- Green dot = healthy / operational
- Yellow/amber = degraded / warning
- Red = down / error
- Gray = unknown / not checked

Always pair color with a text label (accessibility). Show the minimum on the dashboard; tap to expand for details (progressive disclosure).

### "Waiting for Result" Patterns

Ranked by wait duration:

**Under 1 second — Optimistic UI:**
Update immediately as if the action succeeded. Show "Launching..." with the button transitioning to an active state.

**1-10 seconds — Phase Labels:**
Don't use a spinner alone. Show what's happening: "Connecting..." → "Starting Claude..." → "Generating URL..." Each phase transition resets the user's patience clock. Users need feedback within 0.1-0.2 seconds of an action and have ~1 second before they wonder if something broke.

**10+ seconds — Step Counter or Notification:**
Show "Step 2 of 4" rather than a percentage. Allow backgrounding — push a notification when the result is ready. Don't require the user to stare at the screen.

**The URL Result Moment:**
1. Animate the result in (slide-up or expand)
2. Show the URL prominently
3. Provide a giant "Open in Claude" button (primary action shifts)
4. Optionally auto-copy to clipboard

### Reconnection Patterns

**Active Session Cards:**
When something is running, show it prominently at the top of the screen. Demote the launch button. The card shows: project name, branch, time elapsed, and a big tappable URL area.

```
+----------------------------------+
| [green dot] my-project / main    |
|   Started 23 min ago             |
|   [Open in Claude]  [Stop]      |
+----------------------------------+
```

**State Persistence:**
Mobile OSes kill background apps aggressively. On reopen, check: is there a pending or running session? If yes, show it immediately. If the app was closed for >N minutes and the session should be complete, show the result with "Started 12 minutes ago" + the URL.

### General Principles

1. **One giant button.** Primary action should be unmissable and require zero thought to find.
2. **Instant feedback.** Respond to taps within 100ms, even if the real operation takes seconds.
3. **Phase-labeled progress.** Never show a bare spinner. Tell the user what is happening.
4. **Allow backgrounding.** Push a notification when the result is ready.
5. **Traffic-light status.** Green/yellow/red dots with text labels. Never color alone.
6. **Progressive disclosure.** Dashboard shows the minimum; tap to expand details.
7. **Session persistence.** Save state aggressively; assume the app will be killed.
8. **Active session cards.** Running sessions are shown prominently; launch button is demoted.
9. **Haptics on primary actions only.** One tap = one buzz. Confirms without annoying.
10. **The button becomes the progress bar.** Keep the user's eye in one place through the launch-wait-result flow.

### Sources

**UX Research & Patterns:**
- [Smart-Device Apps: 7 Best Practices - NNGroup](https://www.nngroup.com/articles/smart-device-best-practices/)
- [Microinteractions in User Experience - NNGroup](https://www.nngroup.com/articles/microinteractions/)
- [The Role of Animation and Motion in UX - NNGroup](https://www.nngroup.com/articles/animation-purpose-ux/)
- [Skeleton Screens 101 - NNGroup](https://www.nngroup.com/articles/skeleton-screens/)
- [Dashboard Design UX Patterns - Pencil & Paper](https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards)
- [Status Indicators - Carbon Design System](https://carbondesignsystem.com/patterns/status-indicator-pattern/)
- [Progress Indicators in Mobile UX Design - UX Planet](https://uxplanet.org/progress-indicators-in-mobile-ux-design-a141e22f3ea0)
- [Empty States - Carbon Design System](https://carbondesignsystem.com/patterns/empty-states-pattern/)
- [Empty State UX - Smashing Magazine](https://www.smashingmagazine.com/2017/02/user-onboarding-empty-states-mobile-apps/)

**Wait Time Psychology:**
- Nielsen, J. (1993). *Response Times: The 3 Important Limits*
- Harrison, C. et al. (2007). *Rethinking the Progress Bar.* CHI 2007 — accelerating progress bars perceived as faster
- Maister, D. (1985). *The Psychology of Waiting Lines* — uncertain/unexplained waits feel longer
- Hohenstein, J. & Khan, H. (2016). *The Effects of Chat Response Delays on User Experience.* CHI Extended Abstracts

**PWA & Mobile Technical:**
- [PWA App Design - web.dev](https://web.dev/learn/pwa/app-design)
- [Workbox Caching Strategies - Chrome Developers](https://developer.chrome.com/docs/workbox/caching-resources-during-runtime/)
- [Stale-While-Revalidate - web.dev](https://web.dev/articles/stale-while-revalidate)
- [PWA Push Notifications Setup - MobiLoud](https://www.mobiloud.com/blog/pwa-push-notifications)
- [PWAs on iOS Complete Guide - MobiLoud](https://www.mobiloud.com/blog/progressive-web-apps-ios)
- [Patterns for Promoting PWA Installation - web.dev](https://web.dev/articles/promote-install)
- [Offline-First PWAs - MagicBell](https://www.magicbell.com/blog/offline-first-pwas-service-worker-caching-strategies)

**App-to-App Handoff:**
- [Complete Guide to PWA Deep Links - Progressier](https://intercom.help/progressier/en/articles/6902113-complete-guide-to-pwa-deep-links)
- [iOS PWA External Links to Safari - CodeLessGenie](https://www.codelessgenie.com/blog/ios-pwa-how-to-open-external-link-on-mobile-default-safari-not-in-app-browser/)
- [Window Management in PWAs - web.dev](https://web.dev/learn/pwa/windows)
- [What's New on iOS 12.2 for PWAs - Firtman](https://medium.com/@firt/whats-new-on-ios-12-2-for-progressive-web-apps-75c348f8e945)
- [Web Share API in PWAs - Daniel Worsnup](https://www.danielworsnup.com/blog/why-you-should-be-using-the-web-share-api-in-your-pwa/)
