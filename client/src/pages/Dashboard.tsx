import { useState, useEffect } from "react";
import { useEngineState } from "../hooks/useEngineState";
import { StateIndicator } from "../components/StateIndicator";
import { StatsSummary } from "../components/StatsSummary";
import { NotificationCard } from "../components/NotificationCard";
import { api } from "../lib/api";
import type { DailyStats, NotificationEntry } from "../lib/types";

export function Dashboard() {
  const { state, connected } = useEngineState();
  const [stats, setStats] = useState<DailyStats | null>(null);
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);

  useEffect(() => {
    async function fetchData() {
      try {
        const [statsData, notifsData] = await Promise.all([
          api.getDailyStats(),
          api.getNotifications(),
        ]);
        setStats(statsData);
        setNotifications(notifsData);
      } catch (err) {
        console.error("Failed to fetch dashboard data:", err);
      }
    }

    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-100">Dashboard</h1>
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              connected ? "bg-green-500" : "bg-red-500"
            }`}
          />
          <span className="text-xs text-gray-500">
            {connected ? "Engine接続中" : "未接続"}
          </span>
        </div>
      </div>

      {/* State indicator */}
      <div className="flex justify-center">
        <StateIndicator
          state={state?.state ?? null}
          confidence={state?.confidence}
          size="lg"
        />
      </div>

      {/* Sub-states */}
      {state && (
        <div className="flex justify-center gap-6 text-sm text-gray-500">
          <div>
            <span className="text-gray-600">Camera: </span>
            <span className="text-gray-300">{state.camera_state}</span>
          </div>
          <div>
            <span className="text-gray-600">PC: </span>
            <span className="text-gray-300">{state.pc_state}</span>
          </div>
        </div>
      )}

      {/* Stats summary */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 mb-3">
          今日のサマリー
        </h2>
        <StatsSummary stats={stats} />
      </div>

      {/* Recent notifications */}
      {notifications.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 mb-3">
            最近の通知
          </h2>
          <div className="space-y-2">
            {notifications.slice(0, 5).map((notif) => (
              <NotificationCard key={notif.id} notification={notif} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
