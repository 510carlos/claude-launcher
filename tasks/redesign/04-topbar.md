# Top Bar

**File:** `app/frontend/src/components/TopBar.tsx`
**Purpose:** Sticky navigation bar visible on all pages. Shows app identity, workspace count, and page navigation.

## Layout

```
┌──────────────────────────────────────┐
│ Machine                  [Discover]  │
│ 6 workspaces · 1 active  [Updates]   │
└──────────────────────────────────────┘
```

## Visual Design

- **Position:** Sticky, top: 0, z-index: 20
- **Background:** Frosted glass — `rgba(11, 18, 32, 0.88)` with `backdrop-filter: blur(16px)`
- **Border:** 1px solid semi-transparent, border-radius 16px
- **Shadow:** Subtle depth shadow
- **Padding:** 12px
- **Margin-bottom:** 14px

## Left Side: Brand

- **Title:** App name from config (e.g., "Machine") — bold (800 weight), 1rem
- **Subtitle:** "{N} workspaces · {N} active" — muted color, 0.78rem
- **Tap action:** Navigates to dashboard (`/`)

## Right Side: Navigation Buttons

Two pill-shaped buttons stacked in a column with 6px gap.

### Discover Button
- **On dashboard:** Shows "Discover" + badge with count of new compatible environments
  - Badge: blue accent circle, positioned top-right (-6px), 0.7rem bold white text
- **On discovery page:** Shows "Dashboard" (no badge)
- **Style:** 34px height, fully rounded (999px radius), muted text, ghost background

### Updates Button
- **On dashboard:** Shows "Updates"
- **On updates page:** Shows "Dashboard"
- **Same style as Discover button**

## Responsive Behavior

- TopBar stretches full width of the 960px max container
- On very narrow screens, the subtitle may wrap but buttons stay right-aligned
- Touch targets: 34px height buttons (slightly under 48px tap target — could be improved)

## States

- **Dashboard active:** Both nav buttons show their labels (Discover, Updates)
- **Other page active:** Corresponding button changes to "Dashboard"
- **Active sessions > 0:** Count shown in subtitle updates in real-time via signal
