# Updates Page

**Route:** `/updates`
**File:** `app/frontend/src/pages/UpdatesPage.tsx`
**Purpose:** Check if the launcher is behind origin/main and apply updates (git pull + rebuild + restart).

## Layout

```
┌─────────────────────────────┐
│ TopBar (sticky)             │
├─────────────────────────────┤
│ Updates            [Check]  │
│                    [Back]   │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ Up to date      latest  │ │  ← Or "{N} updates available"
│ │ Current: a9a5622        │ │
│ │                         │ │
│ │ (commit list if behind) │ │
│ │                         │ │
│ │ [   Pull & Restart    ] │ │  ← Only if behind
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ Reset App Cache         │ │
│ │ Clears cached assets... │ │
│ │                         │ │
│ │ [    🗑 Clear Cache    ] │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘
```

## Layout Note

Content is wrapped in `.content-narrow` (max-width 600px, centered) — narrower than the main layout for readability.

## Header

- Title: "Updates" (uppercase, muted)
- Right side buttons:
  - "Check" (ghost) — fetches update status. Changes to "Checking..." while active.
  - "Back" (ghost) — returns to dashboard

## Update Status Panel

Shows after a check completes:

**Header row:**
- Left: title + current version hash
  - "Up to date" (if no updates) or "{N} updates available"
  - "Current: {commit hash + message}"
- Right: status pill
  - "latest" (green) if up to date
  - "{N} behind" (yellow) if updates available

**Commit list (if behind):**
- Each pending commit shown as a monospace code block
- Scrollable if many commits

**Action button (if behind):**
- "Pull & Restart" (primary, full-width)
- Changes to "Updating..." while applying
- On success: shows restart message, page reloads after 4 seconds

## Cache Panel

Always visible, separate from update status:

**Header:**
- Title: "Reset App Cache"
- Subtitle: "Clears cached assets so the home screen shortcut picks up new icons and name."

**Action:**
- "Clear Cache" button (danger, full-width)
- Clears all caches, unregisters service worker, clears localStorage
- Shows confirmation message on success

## States

- **No check yet:** Empty state "Could not check for updates."
- **Checking:** Button disabled, text "Checking..."
- **Up to date:** Green "latest" pill, no action button
- **Behind:** Yellow pill, commit list, "Pull & Restart" button
- **Updating:** Button disabled, text "Updating..."
- **Update complete:** Notice message, auto-reload after 4s

## User Flow

1. Tap "Updates" in TopBar
2. Auto-check runs (or tap "Check")
3. If behind: review commit list
4. Tap "Pull & Restart"
5. App pulls latest code, rebuilds frontend, restarts systemd service
6. Page reloads after 4 seconds with new version
