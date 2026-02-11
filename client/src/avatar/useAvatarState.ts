import { useState, useEffect, useRef, useCallback } from "react";
import type { AvatarMode } from "./avatar-state-machine";
import {
  engineStateToAvatarMode,
  createStateDebouncer,
} from "./avatar-state-machine";

type EngineUserState = "focused" | "drowsy" | "distracted" | "away" | "idle";

interface AvatarNotification {
  type: string;
  message: string;
  timestamp: number;
}

const RECONNECT_INTERVAL = 3000;
const DEFAULT_WS_URL = "ws://localhost:18080/ws/state";

const NOTIFICATION_MESSAGES: Record<string, string> = {
  drowsy: "眠気が来ています！立ちましょう",
  distracted: "集中が途切れています",
  over_focus: "休憩しませんか？",
};

async function getWsUrl(): Promise<string> {
  try {
    const engineUrl: string =
      (await (window as any).avatarAPI?.getEngineUrl()) ??
      "http://localhost:18080";
    return engineUrl.replace(/^http/, "ws") + "/ws/state";
  } catch {
    return DEFAULT_WS_URL;
  }
}

export function useAvatarState() {
  const [mode, setMode] = useState<AvatarMode>("hidden");
  const [notification, setNotification] =
    useState<AvatarNotification | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const debouncerRef = useRef(createStateDebouncer(1000));

  const connect = useCallback(async () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const wsUrl = await getWsUrl();

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === "notification" || data.notification_type) {
            const notifType = data.notification_type || data.type;
            const message =
              data.message || NOTIFICATION_MESSAGES[notifType] || "";

            // over_focus triggers stretch mode
            if (notifType === "over_focus") {
              setMode("stretch");
            }

            setNotification({
              type: notifType,
              message,
              timestamp: data.timestamp || Date.now(),
            });

            // Auto-dismiss notification after 5 seconds
            setTimeout(() => setNotification(null), 5000);
          } else if (data.state) {
            const engineState = data.state as EngineUserState;
            const newMode = engineStateToAvatarMode(engineState);
            debouncerRef.current.update(newMode, setMode);
          }
        } catch (err) {
          console.error("Failed to parse avatar WebSocket message:", err);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        reconnectTimerRef.current = setTimeout(
          () => connect(),
          RECONNECT_INTERVAL,
        );
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      reconnectTimerRef.current = setTimeout(
        () => connect(),
        RECONNECT_INTERVAL,
      );
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return { mode, notification, connected };
}
