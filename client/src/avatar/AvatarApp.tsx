import { useState, useEffect } from "react";
import { AvatarCharacter } from "./AvatarCharacter";
import type { AvatarMode, EngineUserState } from "./avatar-state-machine";
import {
  engineStateToAvatarMode,
  createStateDebouncer,
} from "./avatar-state-machine";
import "./avatar.css";

interface AvatarAPI {
  getEngineUrl: () => Promise<string>;
  onStateUpdate: (callback: (data: { state: EngineUserState }) => void) => () => void;
  onNotification: (
    callback: (data: { type: string; message?: string }) => void,
  ) => () => void;
}

declare global {
  interface Window {
    avatarAPI?: AvatarAPI;
  }
}

export const AvatarApp: React.FC = () => {
  const [mode, setMode] = useState<AvatarMode>("hidden");
  const [notification, setNotification] = useState<string | null>(null);

  useEffect(() => {
    const debouncer = createStateDebouncer(1000);

    // Listen for state updates from main process
    const cleanupState = window.avatarAPI?.onStateUpdate((data) => {
      const engineState = data?.state;
      if (engineState) {
        const newMode = engineStateToAvatarMode(engineState);
        debouncer.update(newMode, setMode);
      }
    });

    // Listen for notifications (e.g. over_focus triggers stretch)
    const cleanupNotif = window.avatarAPI?.onNotification((data) => {
      if (data?.type === "over_focus") {
        setMode("stretch");
      }
      if (data?.message) {
        setNotification(data.message);
        setTimeout(() => setNotification(null), 5000);
      }
    });

    return () => {
      cleanupState?.();
      cleanupNotif?.();
    };
  }, []);

  return (
    <div className="avatar-root">
      <AvatarCharacter mode={mode} />
      {notification && <div className="avatar-notification">{notification}</div>}
    </div>
  );
};
