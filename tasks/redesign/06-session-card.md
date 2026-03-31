# Session Card

**File:** `app/frontend/src/components/SessionCard.tsx`
**Purpose:** Represents a single Claude Code session. Shows status, provides the "Open in Claude" button, and allows stopping/deleting.

## Layout — Pending Session

```
┌─────────────────────────────────────┐
│ claude-launcher / main     pending  │  ← Identity + yellow pill
│ swift-fix · just now                │  ← Label · Time
│                                     │
│ ┌─ Progress ──────────────────────┐ │
│ │ ✓ 1. Connecting to workspace... │ │
│ │ → 2. Starting Claude...         │ │  ← Current step (yellow)
│ │   3. Generating URL...          │ │
│ │ ▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░  45%  │ │  ← Animated progress bar
│ │ Usually takes 10–20 seconds     │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [Output] [Stop]                     │
└─────────────────────────────────────┘
```

## Layout — Running Session

```
┌─────────────────────────────────────┐
│ claude-launcher / main     running  │  ← Identity + green pill
│ swift-fix · 2m ago                  │  ← Label · Time
│                                     │
│ ┌─────────────────────────────────┐ │
│ │     🔗 Open in Claude           │ │  ← Full-width green button
│ └─────────────────────────────────┘ │
│ If it doesn't open directly, check  │  ← Hint text (muted, small)
│ your sessions in the Claude app.    │
│                                     │
│ [Output] [Stop]                     │
└─────────────────────────────────────┘
```

## Layout — Stopped/Failed Session (in Recent)

```
┌─────────────────────────────────────┐
│ claude-launcher / main     stopped  │  ← Dimmed (60% opacity)
│ swift-fix · 1h ago                  │
│                                     │
│ [Output] [Delete]                   │
└─────────────────────────────────────┘
```

## Card Header

- **Left side:**
  - Identity: `{workspot}` or `{workspot} / {branch}` (bold, 1rem)
  - Meta: `{label} · {relative time}` + status text for non-running/pending. Muted, 0.8rem.
- **Right side:**
  - Spinner animation (yellow) if pending
  - Status pill:
    - Pending: yellow pill "pending"
    - Running: green pill "running"
    - Failed: red pill "failed"
    - Stopped: no pill (or muted)

## Progress Steps (pending only)

Three fixed steps with animated advancement based on elapsed time:

| Time | Phase | Step Highlighted | Progress Bar |
|------|-------|-----------------|--------------|
| 0-3s | 0 | "Connecting to workspace..." | 15% |
| 3-8s | 1 | "Starting Claude..." | 45% |
| 8s+ | 2 | "Generating URL..." | 80% |

- Completed steps: green checkmark + green text
- Current step: yellow number + yellow text (bold)
- Future steps: gray text
- Progress bar: gradient from yellow to green, animated width transition (1s ease)
- Hint: "Usually takes 10–20 seconds" (centered, muted)

## Open in Claude Button (running only)

- **Full-width** green gradient button
- Min-height: 52px
- Text: "🔗 Open in Claude" (0.95rem, bold)
- Background: green gradient with green border
- Hover: darker green
- **This is the most important element in the entire app** — it's the payoff after launching

## Hint Text (below Open button)

"If it doesn't open directly, check your sessions in the Claude app."
- 0.72rem, muted, centered

## Action Buttons

| Button | When Visible | Action |
|--------|-------------|--------|
| Output | Always | Toggle output log panel |
| Stop | Active sessions (showKill) | SIGTERM → SIGKILL the process |
| Delete | Ended sessions (showDelete) | Remove from history |

## Output Panel

- Toggled by "Output" button
- Max-height: 280px, scrollable
- Dark background, monospace font (0.72rem)
- Shows last 80 lines of session output (ANSI stripped)
- Loading state: "Loading..."
- Failure state: "Failed to load."

## Visual States

| Status | Border | Opacity | Special |
|--------|--------|---------|---------|
| pending | Yellow tint `rgba(245, 158, 11, 0.25)` | 100% | ProgressSteps shown |
| running | Green tint `rgba(34, 197, 94, 0.25)` | 100% | "Open in Claude" button |
| stopped | Default border | 60% | In Recent section |
| failed | Default border | 60% | In Recent section |

## Optimistic UI Behavior

When a user taps "Launch" on a workspace:
1. A temporary pending SessionCard is immediately inserted (before API responds)
2. Phase timer starts (progress animation)
3. Page scrolls to top so the card is visible
4. When API returns: temp card is replaced with real session data
5. On error: temp card is removed, error toast shown
