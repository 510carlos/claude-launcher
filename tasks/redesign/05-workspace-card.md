# Workspace Card

**File:** `app/frontend/src/components/WorkspaceCard.tsx`
**Purpose:** Represents a single workspace (dev environment). The primary interaction point — this is where users launch, resume, and manage sessions.

## Layout

```
┌─────────────────────────────────────┐
│ claude-launcher              Ready  │  ← Name + HealthPill
│ main · Host                         │  ← Branch · Runtime · Active count
│                                     │
│ /home/carlos/git/claude-launcher    │  ← Directory path (monospace)
│                                     │
│ [▶ Launch] [⚙ Options] [🔄 Resume] │  ← Action buttons
│                                     │
│ ┌─ Options Form (if open) ────────┐ │
│ │ Label: [swift-fix    ]          │ │
│ │ Branch: [feature/... ]          │ │
│ │ ☐ Use worktree                  │ │
│ │ [Start with options] [Cancel]   │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─ Conversation Picker (if open) ─┐ │
│ │ Resume a conversation           │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ So I don't want to edit...  │ │ │
│ │ │ 2h ago · 1.8MB              │ │ │
│ │ └─────────────────────────────┘ │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ OK I have a question can... │ │ │
│ │ │ 1d ago · 4.5MB              │ │ │
│ │ └─────────────────────────────┘ │ │
│ │ [Resume] [Cancel]               │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

## Card Header

- **Left side:**
  - Name: workspace name (bold, 1rem)
  - Meta: `{branch} · {runtime}` + active count if > 0. Muted color, 0.8rem.
    - Runtime shows "Host" for host workspaces, container name for Docker
- **Right side:**
  - HealthPill component showing "Ready" (green) or "Needs attention" (red)

## Directory Path

- Full workspace directory path in monospace font
- Muted color, truncated with ellipsis if too long
- Title attribute shows full path on hover/long-press

## Error List (unhealthy workspaces only)

When health checks fail, red error boxes appear:
- "Claude CLI not found"
- "Not authenticated"
- "Git not available"
- "Directory not found"
- "Container not running" / "Host unreachable"

## Action Buttons

Flex row, wraps on overflow. All buttons are `btn-sm` (34px height, 0.75rem).

### Healthy Workspace — No Active Session
| Button | Style | Action |
|--------|-------|--------|
| ▶ Launch | Primary | Quick launch with random label |
| ⚙ Options | Ghost | Toggle OptionsForm |
| 🔄 Resume | Ghost | Toggle ConversationPicker (host only) |

### Healthy Workspace — Has Active Session
| Button | Style | Action |
|--------|-------|--------|
| 🔗 Open | Primary | Open running session URL in new tab |
| ➕ New | Ghost | Start additional session |
| ⚙ Options | Ghost | Toggle OptionsForm |
| 🔄 Resume | Ghost | Toggle ConversationPicker (host only) |

### Healthy Workspace — Has Devcontainer
| Button | Style | Action |
|--------|-------|--------|
| (above buttons) | | |
| 📦 Dev | Ghost | Launch in devcontainer |

### Unhealthy Workspace
| Button | Style | Action |
|--------|-------|--------|
| 🔧 Fix | Primary | Auto-fix issues (start containers, trust workspace) |
| 🔄 Recheck | Ghost | Re-run health checks |

### File-sourced Workspace (removable)
| Button | Style | Action |
|--------|-------|--------|
| 🗑 Remove | Danger | Remove from configuration |

## Inline Panels

Only one panel open at a time — opening Options closes Resume and vice versa.

### Options Form (see also `OptionsForm.tsx`)
- Expands inside the card below the action buttons
- Blue-tinted border and background
- Fields: Label (text), Branch (text), Worktree (checkbox)
- Worktree toggle auto-fills branch with random name
- Buttons: "Start with options" (primary), "Cancel" (ghost)

### Conversation Picker (see `07-conversation-picker.md`)
- Same inline expansion pattern
- Lists past conversations for the workspace
- Tap to select, then "Resume"

## States

| State | Visual |
|-------|--------|
| Healthy, idle | Green "Ready" pill, "Launch" button active |
| Healthy, pending session | "Launch" disabled, shows "⏳ Starting..." |
| Healthy, running session | "Open" replaces "Launch", "New" button appears |
| Unhealthy | Red "Needs attention" pill, error list, Fix/Recheck buttons |
| Options open | OptionsForm expanded inline |
| Resume open | ConversationPicker expanded inline |
