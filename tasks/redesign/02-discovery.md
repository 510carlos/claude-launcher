# Discovery Page

**Route:** `/discover`
**File:** `app/frontend/src/pages/DiscoveryPage.tsx`
**Purpose:** Scan the machine for Docker containers and local git repos that could be Claude Code workspaces. Add compatible ones with a single tap.

## Layout

```
┌─────────────────────────────┐
│ TopBar (sticky)             │
├─────────────────────────────┤
│ Discover Environments       │
│ "Scans Docker containers    │  ← Description text
│  and local repos..."        │
├─────────────────────────────┤
│ ⏳ Scanning environments... │  ← Only during scan
├─────────────────────────────┤
│ Compatible          [3]     │  ← Green count pill
│ "Ready to use."             │
│ ┌───────┐ ┌───────┐        │
│ │ Disc  │ │ Disc  │        │  ← DiscoveryCard components
│ └───────┘ └───────┘        │
├─────────────────────────────┤
│ Needs Setup         [2]     │  ← Yellow count pill
│ "Missing requirements."     │
│ ┌───────┐ ┌───────┐        │
│ │ Disc  │ │ Disc  │        │
│ └───────┘ └───────┘        │
├─────────────────────────────┤
│ Not Ready           [1]     │  ← Gray count pill
│ "Missing most requirements."│
│ ┌───────┐                   │
│ │ Disc  │                   │
│ └───────┘                   │
└─────────────────────────────┘
```

## Header

- Title: "Discover Environments" (uppercase, muted)
- Right side buttons:
  - "Rescan" (primary) — triggers a new scan. Changes to "Scanning..." while active.
  - "Back" (ghost) — returns to dashboard

## Description

Below header: "Scans Docker containers and local repos. Add compatible ones to your workspaces."

## Scanning State

- Info-style notice bar with spinner animation
- Text: "Scanning environments..."
- All buttons disabled during scan

## Results: Three Panels

Results are grouped by compatibility level. Each panel only appears if it has results.

### Compatible Panel
- Header: "Compatible" + green pill with count
- Subtitle: "Ready to use."
- These workspaces have all requirements met (runtime, git, claude CLI, auth)

### Needs Setup Panel
- Header: "Needs Setup" + yellow pill with count
- Subtitle: "Missing requirements."
- These are partially compatible — e.g., has git but no Claude CLI

### Not Ready Panel
- Header: "Not Ready" + gray pill with count
- Subtitle: "Missing most requirements."
- These fail most checks

## Discovery Card

Each scanned environment is shown as a card:

**Header:**
- Name (bold) + directory path (monospace, muted)
- Status pill: "Ready" (green), "Needs setup" (gray), or "Added" (blue tag)
- Activity label if available (e.g., "Active 2d ago")

**Checks row:** Inline list of pass/fail indicators
- ✓ runtime (green) / ✗ runtime (red)
- ✓ git / ✗ git
- ✓ claude / ✗ claude
- ✓ auth / ✗ auth
- ✓ claude setup (if .claude config exists)

**Issues:** Red error boxes listing specific problems (e.g., "Claude CLI not found at claude")

**Action button:**
- "+ Add to Workspaces" (primary, full-width) — if not already added
- "Already added" (ghost, disabled) — if already configured

## Empty State

If no scan has been run: "No scan results yet."

## Auto-Scan Behavior

The page auto-triggers a scan on first visit if no results exist, so the user doesn't need an extra tap.

## User Flow

1. Tap "Discover" in TopBar
2. Scan starts automatically (or tap "Rescan")
3. Results appear grouped by compatibility
4. Tap "+ Add" on a compatible environment
5. Environment appears in dashboard as a new workspace card
6. Tap "Back" to return to dashboard
