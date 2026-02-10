import { useState, useEffect, useRef, useCallback } from "react";
import type { EngineState } from "../lib/types";

const WS_URL = "ws://localhost:18080/ws/state";
const RECONNECT_INTERVAL = 3000;

export function useEngineState() {
  const [state, setState] = useState<EngineState | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        console.log("WebSocket connected");
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as EngineState;
          setState(data);
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

  return { state, connected };
}
