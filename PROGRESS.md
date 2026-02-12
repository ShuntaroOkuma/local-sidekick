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
- [x] Git worktrees created for each member

### Step 1: Transparent Window Foundation (window-dev)
- [x] avatar-window.ts - BrowserWindow creation (transparent, frameless, alwaysOnTop)
- [x] preload-avatar.ts - IPC bridge for avatar window
- [x] avatar.html - HTML entry point
- [x] main.ts - Add avatar window creation + IPC handlers
- [x] electron.vite.config.ts - Add preload-avatar entry
- [x] PR #8 created, reviewed by gemini-code-assist, merged

### Step 2: Avatar Character & Animations (avatar-dev)
- [x] AvatarApp.tsx - React root for avatar window
- [x] AvatarCharacter.tsx - Pure CSS character with animations
- [x] avatar-state-machine.ts - State to animation mapping with debouncer + retreat transition
- [x] avatar.css - 469 lines of polished CSS animations (wake-up, peek, stretch, dozing, retreat)
- [x] avatar-entry.tsx - Vite entry point
- [x] PR #7 created, reviewed by gemini-code-assist, merged

### Step 3+4: Engine Integration + Speech Bubble (integration-dev)
- [x] useAvatarState.ts - WebSocket hook with auto-reconnect and proper cleanup
- [x] SpeechBubble.tsx - One-way message bubble (no buttons, auto-dismiss 5s)
- [x] speech-bubble.css - Fade in/out animations
- [x] notification.ts - Avatar mode conditional (skip OS notification when avatar active)
- [x] PR #6 created, reviewed by gemini-code-assist + reviewer, fix committed, merged
- [x] Merge conflict resolved: avatar-state-machine.ts (combined retreat logic + cancel method)

### Step 5: Integration & Build Verification
- [x] All PRs merged into feat/avatar-poc
- [x] Build succeeds (`electron-vite build` - all modules compiled)
- [ ] Full state cycle test (requires running Engine)
- [ ] Performance check

### Step 6: Testing & Static Analysis (tester team)
- [x] TypeScript type checking (`tsc --noEmit`) - 1 error found
- [x] Build verification (`electron-vite build`) - passes (esbuild more lenient than tsc)
- [x] Static analysis of all 13 avatar-related files
- [x] Interface consistency check (IPC channels, types, state mapping)

**Issues Found & Resolution:**

| # | Severity | File | Issue | Status |
|---|----------|------|-------|--------|
| 1 | CRITICAL | `electron/avatar-window.ts` | `visibleOnAllWorkspaces` not valid as constructor option in Electron 34 | FIXED: moved to `win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })` |
| 2 | CRITICAL | `electron/main.ts` | Production path mismatch for avatar.html | FIXED: corrected to `dist/src/avatar/avatar.html` |
| 3 | WARNING | `src/avatar/AvatarApp.tsx` | Memory leak: debouncer not cleaned up | FIXED: AvatarApp simplified to use `useAvatarState` hook which handles cleanup |
| 4 | WARNING | `src/avatar/AvatarApp.tsx` | Memory leak: notification timer not cleaned up | FIXED: `useAvatarState` hook manages timer cleanup in useEffect |
| 5 | WARNING | `src/avatar/useAvatarState.ts` | `EngineUserState` type duplicated locally | FIXED: imports from `avatar-state-machine.ts` |
| 6 | WARNING | `electron/notification.ts` + `main.ts` | `setAvatarEnabled()` never called | FIXED: called in avatar window `ready-to-show` callback |
| 7 | WARNING | `electron/main.ts` | Dead code: `avatar-toggle` IPC handler | FIXED: removed dead handler |
| 8 | WARNING | `electron/main.ts` | `before-quit` async handler | Known limitation: Electron does not await async handlers. SIGTERM fallback handles this. |
| 9 | INFO | `src/avatar/SpeechBubble.tsx` | Component defined but unused | Kept as optional component for future use |
| 10 | INFO | `src/avatar/useAvatarState.ts` | Hook unused | FIXED: AvatarApp now uses this hook for direct WebSocket connection |

## Build Output
```
dist-electron/main.js           11.44 kB  (includes avatar-window import)
dist-electron/preload-avatar.js  0.66 kB
dist-electron/preload.js         0.89 kB
dist/src/avatar/avatar.html      0.68 kB
dist/assets/avatar-*.css         8.14 kB
dist/assets/avatar-*.js          4.68 kB
```

## Shared Interfaces (Agreed by all members)

```typescript
// IPC channel names
const IPC_CHANNELS = {
  AVATAR_STATE_UPDATE: "avatar-state-update",
  AVATAR_NOTIFICATION: "avatar-notification",
  GET_ENGINE_URL: "get-engine-url",
  GET_AVATAR_ENABLED: "get-avatar-enabled",
  SET_AVATAR_ENABLED: "set-avatar-enabled",
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

## Approaches & Notes

### Attempt 1: Agent Team feature (2025-02-12)
- Used `TeamCreate` + `Task` with `team_name` parameter
- Setting: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.local.json
- **Problem**: All 4 agents were blocked on `permission_request` messages.
- **Resolution**: Team disbanded.

### Attempt 2: Agent Team with bypassPermissions (2026-02-12) - SUCCESS
- Used `TeamCreate` + `Task` with `team_name` and `mode: "bypassPermissions"`
- Team name: `avatar-poc`
- 4 agents: window-dev, avatar-dev, integration-dev, reviewer
- All worked autonomously, created PRs, reviewed, fixed issues, merged
- gemini-code-assist provided automated reviews on all PRs
- One critical issue found (AvatarMode type mismatch) and fixed before merge
- Merge conflict on avatar-state-machine.ts resolved manually
- **Total time**: ~10 minutes from team creation to successful build
