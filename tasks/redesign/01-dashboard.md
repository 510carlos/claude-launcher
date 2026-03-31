# Dashboard Page

**Route:** `/` (default)
**File:** `app/frontend/src/pages/DashboardPage.tsx`
**Purpose:** The main view. Shows everything: active sessions, workspaces, and session history.

## Layout (top to bottom)

```
┌─────────────────────────────┐
│ TopBar (sticky)             │  ← See 04-topbar.md
├─────────────────────────────┤
│ Active Sessions             │  ← Only visible when sessions exist
│ ┌───────┐ ┌───────┐        │
│ │Session│ │Session│         │  ← SessionCard components
│ └───────┘ └───────┘        │
├─────────────────────────────┤
│ Workspaces                  │
│ ┌───────┐ ┌───────┐        │
│ │ WS    │ │ WS    │        │  ← WorkspaceCard components
│ └───────┘ └───────┘        │
│ ┌───────┐ ┌───────┐        │
│ │ WS    │ │ WS    │        │
│ └───────┘ └───────┘        │
├─────────────────────────────┤
│ ▶ Recent (collapsed)        │  ← Collapsible section
│   ┌───────┐ ┌───────┐      │
│   │Session│ │Session│       │  ← Ended session cards
│   └───────┘ └───────┘      │
└─────────────────────────────┘
```

## Section: Active Sessions

**Visibility:** Hidden when no sessions are pending or running. Appears instantly when a launch starts (optimistic UI).

**Header:**
- Label: "Active Sessions" (uppercase, muted, small)
- Count badge: yellow if any pending, green if all running
- "Stop All" button appears when 2+ active sessions

**Content:**
- Responsive grid of SessionCard components (see `06-session-card.md`)
- Cards sorted: running first, then pending, then by creation time descending

**States:**
- Empty (hidden) → User launches → Optimistic pending card appears → Page scrolls to top → Session goes running → "Open in Claude" button visible

## Section: Workspaces

**Header:** "Workspaces" (uppercase, muted, small)

**Content:**
- Responsive grid of WorkspaceCard components (see `05-workspace-card.md`)
- Sort: healthy workspaces first, then by name. "home" workspace always last.

**Empty state:** Shows setup instructions with example `.env` config and a button to go to Discovery.

## Section: Recent Sessions

**Header:** Collapsible toggle row
- Arrow icon (▶/▼) + "Recent" label + count badge (muted)
- "Clear" button on the right (danger style)
- Tapping the header row toggles expand/collapse

**Content (when expanded):**
- Same grid layout as Active Sessions
- Shows stopped and failed sessions
- Each card has a "Delete" button
- "Clear" button removes all at once

**States:**
- Collapsed (default) — only header visible
- Expanded — shows ended session cards
- Empty (hidden) — no ended sessions

## User Flows on This Page

### Quick Launch
1. Tap "Launch" on a workspace card
2. Pending session card appears at top (optimistic)
3. Page scrolls to top automatically
4. Toast: "Starting session in {workspace}..."
5. After ~10-20s: session goes running, "Open in Claude" button appears
6. Tap "Open in Claude" → Claude app opens

### Launch with Options
1. Tap "Options" on a workspace card
2. OptionsForm expands inline within the card
3. Set label, branch, worktree toggle
4. Tap "Start with options"
5. Same flow as Quick Launch

### Resume a Session
1. Tap "Resume" on a host workspace card
2. ConversationPicker expands inline (see `07-conversation-picker.md`)
3. Pick a past conversation
4. Tap "Resume"
5. Same pending → running flow, but with prior context preserved

### Stop a Session
1. Tap "Stop" on a session card
2. Session immediately moves to Recent (optimistic)
3. Toast: "Stopped."

### Open Existing Session
1. If a workspace has a running session, the primary button becomes "Open"
2. Tap "Open" → opens the Claude app URL in new tab
3. "New" button also appears to start an additional session
