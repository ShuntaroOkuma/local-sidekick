import { useState, useEffect } from "react";
import { api } from "../lib/api";
import { useSettings } from "../hooks/useSettings";
import type { DailyStats, DailyReport } from "../lib/types";

export function Report() {
  const { settings } = useSettings();
  const [stats, setStats] = useState<DailyStats | null>(null);
  const [report, setReport] = useState<DailyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const data = await api.getDailyStats();
        setStats(data);
        if (data.report) {
          setReport(data.report);
        }
      } catch (err) {
        console.error("Failed to fetch report data:", err);
        setError("レポートデータの取得に失敗しました");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const data = await api.generateReport();
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

  const today = new Date().toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

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
      <div>
        <h1 className="text-xl font-bold text-gray-100">Daily Report</h1>
        <p className="text-sm text-gray-500 mt-1">{today}</p>
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
        </div>
      ) : (
        <div className="bg-gray-800/50 rounded-xl p-8 text-center">
          <p className="text-gray-400 mb-4">
            今日のレポートはまだ生成されていません
          </p>
          {stats && (
            <p className="text-xs text-gray-600 mb-4">
              集中 {Math.round(stats.focused_minutes)}分 /
              散漫 {Math.round(stats.distracted_minutes)}分 /
              眠気 {Math.round(stats.drowsy_minutes)}分
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
