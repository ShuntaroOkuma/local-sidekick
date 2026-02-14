import { useState, useEffect } from "react";
import { api } from "../lib/api";
import { useSettings } from "../hooks/useSettings";
import type { DailyStats, DailyReport } from "../lib/types";

// ローカル日付をYYYY-MM-DD形式で取得するヘルパー
function toLocalDateString(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function Report() {
  const { settings } = useSettings();
  const [stats, setStats] = useState<DailyStats | null>(null);
  const [report, setReport] = useState<DailyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedDate, setSelectedDate] = useState<string>(() => {
    return toLocalDateString(new Date());
  });
  // reportDates is fetched for future calendar/date picker UI
  const [reportDates, setReportDates] = useState<string[]>([]);

  const todayStr = toLocalDateString(new Date());
  const isToday = selectedDate === todayStr;

  const navigateDate = (delta: number) => {
    const current = new Date(selectedDate + "T00:00:00");
    current.setDate(current.getDate() + delta);
    const next = toLocalDateString(current);
    if (next > todayStr) return;
    setSelectedDate(next);
  };

  useEffect(() => {
    api.listReports().then(setReportDates).catch((err) => {
      console.error("Failed to fetch report dates:", err);
    });
  }, []);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      setReport(null);
      try {
        if (isToday) {
          const data = await api.getDailyStats();
          setStats(data);
          if (data.report) {
            setReport(data.report);
          }
        } else {
          // 過去日: ローカル統計を取得してデータ有無を判定
          try {
            const statsData = await api.getDailyStats(selectedDate);
            setStats(statsData);
          } catch {
            setStats(null);
          }
          // クラウドからレポート取得
          try {
            const data = await api.getReport(selectedDate);
            setReport(data);
          } catch (err) {
            // 404 (レポート無し) は無視、それ以外は外側catchに伝播
            const message = err instanceof Error ? err.message : "";
            if (!message.includes("404")) {
              throw err;
            }
          }
        }
      } catch (err) {
        console.error("Failed to fetch report data:", err);
        setError("レポートデータの取得に失敗しました");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [selectedDate]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const data = await api.generateReport(selectedDate);
      setStats(data);
      if (data.report) {
        setReport(data.report);
      }
    } catch (err) {
      console.error("Failed to generate report:", err);
      setError("レポート生成に失敗しました。しばらくしてから再試行してください。");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-gray-100">Daily Report</h1>
        <div className="bg-gray-800 rounded-lg p-8 animate-pulse h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Date Navigation */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-100">Daily Report</h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigateDate(-1)}
            className="p-1.5 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-gray-200 transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          <span className="text-sm text-gray-300 min-w-[120px] text-center">
            {isToday
              ? "今日"
              : new Date(selectedDate + "T00:00:00").toLocaleDateString(
                  "ja-JP",
                  {
                    month: "long",
                    day: "numeric",
                  }
                )}
          </span>
          <button
            onClick={() => navigateDate(1)}
            disabled={isToday}
            className="p-1.5 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-gray-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {report && settings.sync_enabled && stats?.report_source === "local" && (
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4">
          <p className="text-sm text-yellow-400">
            Cloud Run に接続できませんでした。ローカルレポートを表示しています。
          </p>
        </div>
      )}

      {report ? (
        <div className="space-y-4">
          {/* Summary */}
          <div className="bg-gray-800/50 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-blue-400 mb-2">
              サマリー
            </h2>
            <p className="text-gray-300 text-sm leading-relaxed">
              {report.summary}
            </p>
          </div>

          {/* Pattern */}
          {report.pattern && (
            <div className="bg-gray-800/50 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-purple-400 mb-2">
                集中パターン
              </h2>
              <p className="text-gray-300 text-sm leading-relaxed">
                {report.pattern}
              </p>
            </div>
          )}

          {/* Highlights */}
          {report.highlights.length > 0 && (
            <div className="bg-gray-800/50 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-green-400 mb-2">
                ハイライト
              </h2>
              <ul className="space-y-1.5">
                {report.highlights.map((item, i) => (
                  <li
                    key={i}
                    className="text-sm text-gray-300 flex items-start gap-2"
                  >
                    <span className="text-green-500 mt-0.5">●</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Concerns */}
          {report.concerns.length > 0 && (
            <div className="bg-gray-800/50 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-yellow-400 mb-2">
                気になるポイント
              </h2>
              <ul className="space-y-1.5">
                {report.concerns.map((item, i) => (
                  <li
                    key={i}
                    className="text-sm text-gray-300 flex items-start gap-2"
                  >
                    <span className="text-yellow-500 mt-0.5">▲</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Tomorrow tip */}
          {report.tomorrow_tip && (
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-blue-400 mb-2">
                明日の一手
              </h2>
              <p className="text-sm text-gray-300">{report.tomorrow_tip}</p>
            </div>
          )}

          {/* Regenerate button (today only) */}
          {isToday && (
            <div className="flex justify-end">
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-4 py-1.5 text-xs text-gray-500 hover:text-gray-300 hover:bg-gray-800 disabled:text-gray-700 rounded-lg transition-colors"
              >
                {generating ? "再生成中..." : "レポートを再生成"}
              </button>
            </div>
          )}
        </div>
      ) : !isToday ? (
        <div className="bg-gray-800/50 rounded-xl p-8 text-center">
          {!settings.sync_enabled ? (
            <p className="text-gray-400">
              過去のレポートを表示するにはCloud同期を有効にしてください
            </p>
          ) : stats && (stats.focused_minutes > 0 || stats.distracted_minutes > 0 || stats.drowsy_minutes > 0) ? (
            <>
              <p className="text-gray-400 mb-4">
                この日のレポートはまだ生成されていません
              </p>
              <p className="text-xs text-gray-600 mb-4">
                集中 {Math.round(stats.focused_minutes)}分 /
                散漫 {Math.round(stats.distracted_minutes)}分 /
                眠気 {Math.round(stats.drowsy_minutes)}分
              </p>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {generating ? "生成中..." : "レポートを生成"}
              </button>
            </>
          ) : (
            <p className="text-gray-400">この日のデータがありません</p>
          )}
        </div>
      ) : (
        <div className="bg-gray-800/50 rounded-xl p-8 text-center">
          <p className="text-gray-400 mb-4">
            今日のレポートはまだ生成されていません
          </p>
          {stats && (
            <p className="text-xs text-gray-600 mb-4">
              集中 {Math.round(stats.focused_minutes)}分 / 散漫{" "}
              {Math.round(stats.distracted_minutes)}分 / 眠気{" "}
              {Math.round(stats.drowsy_minutes)}分
            </p>
          )}
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {generating ? "生成中..." : "レポートを生成"}
          </button>
        </div>
      )}
    </div>
  );
}
