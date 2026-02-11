/**
 * Minimal avatar state machine for Engine integration.
 * The canonical version lives in avatar-dev's branch;
 * this duplicate will be resolved when both PRs merge into feat/avatar-poc.
 */

export type AvatarMode =
  | "hidden"
  | "idle"
  | "focus"
  | "drowsy"
  | "break"
  | "stretch";

type EngineUserState = "focused" | "drowsy" | "distracted" | "away" | "idle";

const STATE_MAP: Record<EngineUserState, AvatarMode> = {
  focused: "focus",
  drowsy: "drowsy",
  distracted: "break",
  away: "hidden",
  idle: "idle",
};

export function engineStateToAvatarMode(state: EngineUserState): AvatarMode {
  return STATE_MAP[state] ?? "idle";
}

/**
 * Simple debouncer to avoid rapid avatar-mode flicker.
 * Calls `setter` only after the new mode has been stable for `delayMs`.
 */
export function createStateDebouncer(delayMs: number) {
  let timer: ReturnType<typeof setTimeout> | null = null;

  return {
    update(newMode: AvatarMode, setter: (m: AvatarMode) => void) {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        setter(newMode);
        timer = null;
      }, delayMs);
    },
  };
}
