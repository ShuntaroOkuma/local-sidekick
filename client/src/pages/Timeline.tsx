import { useState, useEffect } from "react";
import { TimelineChart } from "../components/TimelineChart";
import { api } from "../lib/api";
import type { HistoryEntry, NotificationEntry } from "../lib/types";

const START_HOUR = 0;
const END_HOUR = 24;

function formatDateLabel(date: Date): string {
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/** Build Unix timestamp range for a given date (full day) */
function buildTimeRange(date: Date): { start: number; end: number } {
  const start = new Date(date);
  start.setHours(START_HOUR, 0, 0, 0);
  const end = new Date(date);
  end.setHours(END_HOUR, 0, 0, 0);
  return {
    start: Math.floor(start.getTime() / 1000),
    end: Math.floor(end.getTime() / 1000),
  };
}

export function Timeline() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState(() => new Date());

  const isToday = isSameDay(selectedDate, new Date());

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const range = buildTimeRange(selectedDate);
        const [historyData, notifsData] = await Promise.all([
          api.getHistory(range),
          api.getNotifications(range),
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
    if (isToday) {
      const interval = setInterval(fetchData, 60000);
      return () => clearInterval(interval);
    }
  }, [selectedDate]);

  function goToPreviousDay() {
    setSelectedDate((prev) => {
      const next = new Date(prev);
      next.setDate(next.getDate() - 1);
      return next;
    });
  }

  function goToNextDay() {
    if (isToday) return;
    setSelectedDate((prev) => {
      const next = new Date(prev);
      next.setDate(next.getDate() + 1);
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-100">Timeline</h1>
        {/* Date navigation */}
        <div className="flex items-center gap-3 mt-1">
          <button
            onClick={goToPreviousDay}
            className="text-gray-500 hover:text-gray-300 transition-colors p-1"
            aria-label="前の日"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
          <p className="text-sm text-gray-500">
            {formatDateLabel(selectedDate)}
            {isToday && (
              <span className="ml-2 text-xs text-blue-400">today</span>
            )}
          </p>
          <button
            onClick={goToNextDay}
            disabled={isToday}
            className={`p-1 transition-colors ${
              isToday
                ? "text-gray-700 cursor-not-allowed"
                : "text-gray-500 hover:text-gray-300"
            }`}
            aria-label="次の日"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        </div>
      </div>

      {loading && (
        <div className="bg-gray-800 rounded-lg p-8 animate-pulse h-64" />
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
                startHour={START_HOUR}
                endHour={END_HOUR}
              />
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>データがまだありません</p>
                <p className="text-xs mt-1">
                  {isToday
                    ? "Engineが起動するとデータが蓄積されます"
                    : "この日のデータはありません"}
                </p>
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
