# Claude Launcher — UX Redesign Overview

## What Is This App?

Claude Launcher is a **session orchestrator** for Claude Code. It lets you start, manage, and resume Claude Code remote-control sessions across multiple workspaces — all from your phone.

It does NOT render conversations or provide a terminal. It invokes `claude remote-control`, captures the URL, and hands you off to the Claude app where the real work happens.

## Primary User

A developer on their phone (couch, commute, meetings) who has one or more dev machines running 24/7. They want to tap a button and be coding in Claude within seconds.

## Core Flow

```
Open app on phone → See workspaces → Tap Launch → Wait ~10s → Tap "Open in Claude" → Working
```

## Pages

| Page | File | Purpose |
|------|------|---------|
| Dashboard | `01-dashboard.md` | Main view: active sessions, workspace grid, recent sessions |
| Discovery | `02-discovery.md` | Scan and add new workspaces |
| Updates | `03-updates.md` | Check for and apply app updates |

## Shared Components

| Component | File | Used On |
|-----------|------|---------|
| Top Bar | `04-topbar.md` | All pages (sticky navigation) |
| Workspace Card | `05-workspace-card.md` | Dashboard |
| Session Card | `06-session-card.md` | Dashboard (active + recent) |
| Conversation Picker | `07-conversation-picker.md` | Dashboard (resume flow) |

## Design System

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#0b1220` | Page background |
| `--surface` | `rgba(15, 23, 42, 0.92)` | Card backgrounds |
| `--surface-2` | `rgba(30, 41, 59, 0.9)` | Secondary surfaces, code paths |
| `--accent` | `#60a5fa` | Primary actions, focus rings |
| `--green` | `#22c55e` | Running/healthy/success states |
| `--yellow` | `#f59e0b` | Pending/warning states |
| `--red` | `#f87171` | Failed/error/danger states |
| `--muted` | `#94a3b8` | Secondary text, metadata |
| `--text` | `#e5eefc` | Primary text |
| `--border` | `rgba(148, 163, 184, 0.18)` | Card/element borders |
| `--r` | `16px` | Card border-radius |
| `--r-sm` | `12px` | Small element radius |
| `--tap` | `48px` | Minimum touch target |

**Typography:** Inter / system-ui, 15px base, 1.5 line-height

**Layout:** Max 960px centered. 1 col (mobile) → 2 col (720px+) → 3 col (1000px+)

**Theme:** Dark navy. Optimized for low-light phone usage.
