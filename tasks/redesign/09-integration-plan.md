# Integration Plan: Glassmorphism Redesign

## What We Have

### Working App (Preact + Signals)
- `UnifiedCard.tsx` — already built with idle/pending/running/unhealthy states, "..." menu, inline OptionsForm/ConversationPicker
- `WorkspaceGrid.tsx` — already uses UnifiedCard, sorts active workspaces first
- `DashboardPage.tsx` — already simplified (no ActiveSessions section)
- `SessionCard.tsx` — simplified for history-only (Recent section)
- All backend APIs working (launch, resume, kill, conversations)

### Design Mockup (`tasks/redesign/mockup/index.html`)
- Glassmorphism CSS with design tokens
- Hero status tile with animated ring
- Full-width glass cards with Launch + "..." menu
- Expanded menu with staggered animation
- Floating bottom nav pill
- Background gradient orbs with drift animation
- Card state transitions (idle → pending → running)
- All animations prototyped and working

## Integration Steps

### Phase 1: CSS Rewrite
Replace `app.css` design tokens and base styles with glassmorphism system:
- Background: gradient + orb elements
- Glass panel base: backdrop-filter blur, translucent bg, luminous borders
- Card styles: glass treatment, inner top-edge highlight
- Button styles: glass buttons with blue accent glow
- Badge styles: glow halos on Ready/Needs attention
- All animation keyframes from mockup

### Phase 2: Layout Changes
- **Remove TopBar** — replace with Hero Status Tile component
- **Add BottomNav** — new component, floating glass pill, handles routing
- **Update App.tsx** — new layout: hero tile at top, page content, bottom nav fixed

### Phase 3: Component Updates
- **UnifiedCard** — add glassmorphism classes, wire up CSS transitions for state changes, add "..." menu animation (currently uses signal toggle, needs CSS transition classes)
- **HealthPill** — update styling to match glass badge design
- **ProgressSteps** — update to match mockup progress style
- **OptionsForm** — glass treatment on the form panel
- **ConversationPicker** — glass treatment

### Phase 4: New Components
- **HeroTile** — status ring with animated SVG, workspace count, active count
- **BottomNav** — floating glass pill with Workspaces/Discover/Updates, active dot animation

### Phase 5: Animations
- Background orb drift (CSS only)
- Card appear stagger on load
- Card state border transitions
- Menu expand/collapse stagger
- Open-in-Claude pulse glow
- Button press feedback
- Status ring fill animation
- Bottom nav appear animation

## Key Decisions Needed
1. Keep TopBar AND add BottomNav, or fully replace TopBar?
2. Orb elements: static CSS gradients or actual DOM elements?
3. Background image tile vs CSS-only background?
4. Service worker / PWA manifest updates for new theme color?

## Risk Mitigation
- Work in the mockup dir first to validate each phase
- Keep old CSS classes until new ones are verified
- Build + screenshot after each phase
- Test on actual phone between phases
