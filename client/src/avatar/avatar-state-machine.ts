export type AvatarMode =
  | "hidden"
  | "wake-up"
  | "peek"
  | "stretch"
  | "dozing"
  | "retreat";

export type EngineUserState =
  | "focused"
  | "drowsy"
  | "distracted"
  | "over_focus"
  | "away"
  | "idle";

/** Map engine states to avatar animation modes */
export function engineStateToAvatarMode(
  engineState: EngineUserState,
): AvatarMode {
  switch (engineState) {
    case "focused":
      return "hidden";
    case "drowsy":
      return "wake-up";
    case "distracted":
      return "peek";
    case "over_focus":
      return "stretch";
    case "away":
    case "idle":
      return "dozing";
    default:
      return "hidden";
  }
}

/**
 * Debounce state changes to prevent rapid flickering between modes.
 * Hiding transitions play a retreat animation first.
 */
export function createStateDebouncer(delayMs: number = 1000) {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let currentMode: AvatarMode = "hidden";

  return {
    update(newMode: AvatarMode, callback: (mode: AvatarMode) => void): void {
      if (newMode === currentMode) return;

      if (timeoutId) clearTimeout(timeoutId);

      // When returning to hidden, play retreat first then hide
      if (newMode === "hidden") {
        currentMode = "retreat";
        callback("retreat");
        timeoutId = setTimeout(() => {
          currentMode = "hidden";
          callback("hidden");
        }, 1500);
        return;
      }

      // Debounce showing transitions to avoid flicker
      timeoutId = setTimeout(() => {
        currentMode = newMode;
        callback(newMode);
      }, delayMs);
    },

    forceUpdate(newMode: AvatarMode, callback: (mode: AvatarMode) => void): void {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      currentMode = newMode;
      callback(newMode);
    },

    getCurrentMode(): AvatarMode {
      return currentMode;
    },

    cancel(): void {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
    },
  };
}
