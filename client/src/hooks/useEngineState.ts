import { useState, useEffect, useRef, useCallback } from "react";
import type { EngineState } from "../lib/types";

const DEFAULT_WS_URL = "ws://localhost:18080/ws/state";
const RECONNECT_INTERVAL = 3000;

async function getWsUrl(): Promise<string> {
  try {
    const engineUrl: string =
      await (window as any).electronAPI?.getEngineUrl() ?? "http://localhost:18080";
    return engineUrl.replace(/^http/, "ws") + "/ws/state";
  } catch {
    return DEFAULT_WS_URL;
  }
}

export interface Notification {
  type: string;
  message: string;
  timestamp: number;
}

export function useEngineState() {
  const [state, setState] = useState<EngineState | null>(null);
  const [notification, setNotification] = useState<Notification | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(async () => {
    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const wsUrl = await getWsUrl();

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log("WebSocket connected");
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // Distinguish state updates from notification messages
          if (data.type === "notification") {
            setNotification({
              type: data.notification_type,
              message: data.message,
              timestamp: data.timestamp,
            });
          } else {
            setState(data as EngineState);
          }
        } catch (err) {
          console.error("Failed to parse WebSocket message:", err);
        }
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected");
        setConnected(false);
        wsRef.current = null;

        // Schedule reconnect
        reconnectTimerRef.current = setTimeout(() => {
          console.log("Attempting WebSocket reconnect...");
          connect();
        }, RECONNECT_INTERVAL);
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        ws.close();
      };

      wsRef.current = ws;
    } catch (err) {
      console.error("Failed to create WebSocket:", err);
      // Schedule reconnect
      reconnectTimerRef.current = setTimeout(() => {
        connect();
      }, RECONNECT_INTERVAL);
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { state, notification, connected };
}
