# Animation Spec

All animations in the glassmorphism redesign. Prototyped and working in `mockup/index.html`.

## Page Load

- **Card stagger-in:** Cards fade up (translateY 16px → 0, opacity 0 → 1) with 80ms delay between each. Duration: 500ms ease-out.
- **Bottom nav slide-up:** 400ms ease-out, 350ms delay after cards start.
- **Hero tile:** Same as card appear, first in sequence (50ms delay).

## Background

- **Orb drift:** Two gradient orbs float continuously. Orb 1: 18s cycle, Orb 2: 22s cycle. Translate 20-25px in alternating directions. `ease-in-out infinite alternate`.

## Card State Transitions

### Idle → Pending
- Border color: neutral → yellow (400ms ease)
- Box-shadow: adds yellow glow (400ms)
- Badge: crossfade to "pending" yellow
- Path element: fade out + collapse (opacity 0, max-height 0, 300ms)
- Progress section: fade in + expand (300ms)
- Progress bar: width animates (1s ease)

### Pending → Running
- Border color: yellow → green (400ms)
- **Green flash:** border glow pulses bright then settles (800ms, `border-flash-green`)
- Badge: crossfade to "running" green
- Progress: collapse out (300ms)
- "Open in Claude" button: appears (300ms fade)
- Status ring: stroke-dashoffset animates to fill (800ms ease-out), stroke color → green (400ms)
- Count number: scale bump 1.0 → 1.3 → 1.0 (400ms)

### Running → Stopped
- Card fades to 60% opacity (300ms)
- Moves to Recent section

## Interactive Elements

### "Open in Claude" Button
- **Pulse glow:** Continuous 2.5s breathe cycle on box-shadow (green, 12px → 24px → 12px). Draws the eye.

### "..." Menu
- **Expand:** max-height 0→200px (300ms), opacity 0→1 (200ms). Menu rows stagger in: each translateY(-8px)→0 + opacity 0→1 with 50ms delay between rows.
- **Collapse:** Reverse, slightly faster (250ms).
- **"..." button:** border highlights blue when menu is open.

### All Buttons
- **Press feedback:** scale(0.96) on mousedown/touchstart, back to 1.0 on release. Duration: 100ms.

### Bottom Nav
- **Active dot:** slides horizontally to active item (300ms cubic-bezier).
- **Active icon:** scale 1.0 → 1.1 (200ms).

## Status Ring (Hero Tile)

- **Fill animation:** `stroke-dashoffset` transitions over 800ms when active count changes.
- **Color:** muted blue (#60a5fa) when idle → green (#22c55e) when active.
- **Count bump:** scale animation on number change (400ms).

## What NOT to Animate

- No parallax
- No spring physics on everything
- No delays over 400ms
- No animation on every re-render — only on actual state transitions
- No page transition animations initially (can add later)
