import { useState, useEffect } from "react";
import { useEngineState } from "../hooks/useEngineState";
import { StateIndicator } from "../components/StateIndicator";
import { StatsSummary } from "../components/StatsSummary";
import { api } from "../lib/api";
import type { DailyStats } from "../lib/types";

export function Dashboard() {
  const { state, connected } = useEngineState();
  const [stats, setStats] = useState<DailyStats | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const statsData = await api.getDailyStats();
        setStats(statsData);
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

      {/* Judgment info */}
      {state && (
        <div className="text-center space-y-1">
          <div className="flex justify-center items-center gap-2 text-xs">
            <span
              className={`px-2 py-0.5 rounded-full font-medium ${
                state.source === "llm"
                  ? "bg-purple-500/20 text-purple-300"
                  : "bg-blue-500/20 text-blue-300"
              }`}
            >
              {state.source === "llm" ? "LLM判定" : "ルール判定"}
            </span>
          </div>
          {state.reasoning && (
            <p className="text-xs text-gray-500 max-w-xs mx-auto">
              {state.reasoning}
            </p>
          )}
        </div>
      )}

      {/* Stats summary */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 mb-3">
          今日のサマリー
        </h2>
        <StatsSummary stats={stats} />
      </div>

    </div>
  );
}
