# Conversation Picker (Resume Flow)

**File:** `app/frontend/src/components/ConversationPicker.tsx`
**Purpose:** Let users pick a previous Claude conversation to resume via remote-control. Experimental feature for recovering context from dropped sessions.

## Layout

```
┌─────────────────────────────────────┐
│ Resume a conversation               │  ← Title
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ So I don't want to edit it just │ │  ← 2-line preview
│ │ yet but what I do is sometimes  │ │
│ │ 2h ago · 1.8MB                  │ │  ← Time + file size
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ OK I have a question can you    │ │  ← Selected (blue border)
│ │ check out Main and make sure... │ │
│ │ 1d ago · 4.5MB                  │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ # Session Handoff — 2026-03-16 │ │
│ │ ## What Was Accomplished...     │ │
│ │ 14d ago · 6.1MB                 │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [Resume] [Cancel]                   │
└─────────────────────────────────────┘
```

## Container

- Same `.form-area.open` styling as OptionsForm
- Blue-tinted border and background
- Expands inline within the WorkspaceCard

## Title

"Resume a conversation" — bold, 0.88rem

## Conversation List

- `.conversation-list`: flex column, gap 8px
- Max-height: 320px, scrollable (overflow-y: auto)
- Fetches from `GET /api/workspots/{name}/conversations?limit=15`

### Conversation Row

Each row shows one past Claude session:

- **Preview text:** First user message, up to 2 lines (CSS line-clamp)
  - Font: 0.85rem, primary text color, 1.4 line-height
- **Meta line:** `{relative time} · {file size}`
  - Font: 0.75rem, muted color
  - Size formatted as B/KB/MB

**Row styling:**
- Padding: 12px, min-height: 48px (tap target)
- Border: 1px solid border color
- Background: surface-2
- Border-radius: 12px

**Row states:**
| State | Visual |
|-------|--------|
| Default | Standard border |
| Hover | Blue-tinted border |
| Selected | Blue (accent) border + subtle blue background |

## Action Buttons

- **Resume** (primary) — disabled until a conversation is selected. Triggers the PTY-based resume flow.
- **Cancel** (ghost) — closes the picker

## Content States

| State | What Shows |
|-------|-----------|
| Loading | "Loading..." text (muted) |
| Empty | "No previous conversations found." (muted) |
| Loaded | Scrollable list of conversation rows |

## Data Source

Sessions are read from `~/.claude/projects/<project-slug>/*.jsonl` on the server. Empty/forked sessions (from prior resumes) are filtered out. Only sessions with a real first user message appear.

## How Resume Works (behind the scenes)

1. User selects a conversation and taps "Resume"
2. Frontend sends `POST /api/sessions/resume` with workspot + conversation_id
3. Backend spawns `claude --resume <id> --fork-session` via PTY
4. Sends `/remote-control` command after detecting the prompt
5. Captures the remote-control URL
6. Returns URL to frontend
7. Session appears in Active Sessions with "Open in Claude" button
8. Claude app opens with full prior context (messages don't display, but model remembers everything)

## Limitations

- **Host runtime only** — Docker workspaces don't show the Resume button
- **No visual history in Claude app** — old messages aren't rendered, but the model has full context
- **8KB scan window** — very large sessions where the first user message is deep in the file may show as empty (filtered out)
