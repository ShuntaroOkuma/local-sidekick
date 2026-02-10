import { useState, useEffect } from "react";
import { TimelineChart } from "../components/TimelineChart";
import { api } from "../lib/api";
import type { HistoryEntry, NotificationEntry } from "../lib/types";

export function Timeline() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const [historyData, notifsData] = await Promise.all([
          api.getHistory(),
          api.getNotifications(),
        ]);
        setHistory(historyData);
        setNotifications(notifsData);
      } catch (err) {
        console.error("Failed to fetch timeline data:", err);
        setError("タイムラインデータの取得に失敗しました");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const today = new Date().toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-100">Timeline</h1>
        <p className="text-sm text-gray-500 mt-1">{today}</p>
      </div>

      {loading && (
        <div className="bg-gray-800 rounded-lg p-8 animate-pulse h-32" />
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="bg-gray-800/50 rounded-xl p-6">
            <h2 className="text-sm font-semibold text-gray-400 mb-4">
              状態タイムライン
            </h2>
            {history.length > 0 ? (
              <TimelineChart
                history={history}
                notifications={notifications}
              />
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>データがまだありません</p>
                <p className="text-xs mt-1">Engineが起動するとデータが蓄積されます</p>
              </div>
            )}
          </div>

          {/* Notification log */}
          {notifications.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-400 mb-3">
                通知ログ
              </h2>
              <div className="space-y-1">
                {notifications.map((notif) => {
                  const time = new Date(
                    notif.timestamp * 1000
                  ).toLocaleTimeString("ja-JP", {
                    hour: "2-digit",
                    minute: "2-digit",
                  });
                  return (
                    <div
                      key={notif.id}
                      className="flex items-center gap-3 text-sm py-1.5"
                    >
                      <span className="text-gray-500 font-mono text-xs w-12">
                        {time}
                      </span>
                      <span className="text-gray-300">{notif.type}</span>
                      {notif.user_action && (
                        <span className="text-xs text-gray-600">
                          ({notif.user_action})
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
