/**
 * Minimal avatar state machine for Engine integration.
 * The canonical version lives in avatar-dev's branch;
 * this duplicate will be resolved when both PRs merge into feat/avatar-poc.
 */

export type AvatarMode =
  | "hidden"
  | "wake-up"
  | "peek"
  | "stretch"
  | "dozing"
  | "retreat";

type EngineUserState = "focused" | "drowsy" | "distracted" | "away" | "idle";

const STATE_MAP: Record<EngineUserState, AvatarMode> = {
  focused: "hidden",
  drowsy: "wake-up",
  distracted: "peek",
  away: "dozing",
  idle: "dozing",
};

export function engineStateToAvatarMode(state: EngineUserState): AvatarMode {
  return STATE_MAP[state] ?? "dozing";
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
    cancel() {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    },
  };
}
