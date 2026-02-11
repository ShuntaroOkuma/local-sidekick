# Avatar PoC - Progress Tracker

## Overview
Desktop avatar (sidekick character) that delivers notifications visually instead of OS native notifications.
See [docs/avatar-poc-plan.md](docs/avatar-poc-plan.md) for full plan.

## Team Members & Branches

| Member | Branch | Worktree | Scope |
|--------|--------|----------|-------|
| window-dev | `feat/avatar-poc-window` | `local-sidekick-window` | Step 1: Transparent BrowserWindow foundation |
| avatar-dev | `feat/avatar-poc-avatar` | `local-sidekick-avatar` | Step 2: Avatar character & animations |
| integration-dev | `feat/avatar-poc-integration` | `local-sidekick-integration` | Step 3+4: Engine WebSocket + Speech bubble |
| reviewer | - | - | PR reviews |

## PR Flow
All PRs target `feat/avatar-poc` branch. After all merged, `feat/avatar-poc` will be PRed to `main`.

## Status

### Step 0: Branch & Worktree Setup
- [x] Base branch `feat/avatar-poc` created from main
- [x] PROGRESS.md created
- [ ] Git worktrees created for each member

### Step 1: Transparent Window Foundation (window-dev)
- [ ] avatar-window.ts - BrowserWindow creation (transparent, frameless, alwaysOnTop)
- [ ] preload-avatar.ts - IPC bridge for avatar window
- [ ] avatar.html - HTML entry point
- [ ] main.ts - Add avatar window creation + IPC handlers
- [ ] electron.vite.config.ts - Add preload-avatar entry
- [ ] PR created and reviewed

### Step 2: Avatar Character & Animations (avatar-dev)
- [ ] AvatarApp.tsx - React root for avatar window
- [ ] AvatarCharacter.tsx - Canvas-based character with animations
- [ ] avatar-state-machine.ts - State to animation mapping
- [ ] CSS/sprite assets
- [ ] avatar-entry.tsx - Vite entry point
- [ ] PR created and reviewed

### Step 3+4: Engine Integration + Speech Bubble (integration-dev)
- [ ] useAvatarState.ts - WebSocket hook for avatar
- [ ] SpeechBubble.tsx - One-way message bubble (no buttons, auto-dismiss)
- [ ] notification.ts - Avatar mode conditional
- [ ] PR created and reviewed

### Step 5: Integration Test & Adjustments
- [ ] All PRs merged into feat/avatar-poc
- [ ] Build succeeds
- [ ] Full state cycle test
- [ ] Performance check

## Shared Interfaces (Agreed by all members)

```typescript
// IPC channel names
const IPC_CHANNELS = {
  AVATAR_STATE_UPDATE: "avatar-state-update",
  AVATAR_NOTIFICATION: "avatar-notification",
  AVATAR_TOGGLE: "avatar-toggle",
  GET_ENGINE_URL: "get-engine-url",
} as const;

// Avatar states (from Engine → Avatar)
type AvatarMode = "hidden" | "wake-up" | "peek" | "stretch" | "dozing" | "retreat";

// State mapping
// focused → hidden
// drowsy → wake-up
// distracted → peek
// over_focus → stretch
// away/idle → dozing
// transition back to focused → retreat → hidden
```

## Failed Approaches & Notes
(Record failed approaches here for future reference)
