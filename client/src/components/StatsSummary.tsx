import type { DailyStats } from "../lib/types";

interface StatsSummaryProps {
  stats: DailyStats | null;
}

interface StatItem {
  label: string;
  value: number;
  color: string;
  bgColor: string;
}

function formatMinutes(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours > 0) {
    return `${hours}h ${mins}m`;
  }
  return `${mins}m`;
}

export function StatsSummary({ stats }: StatsSummaryProps) {
  if (!stats) {
    return (
      <div className="grid grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="bg-gray-800 rounded-lg p-3 animate-pulse h-20"
          />
        ))}
      </div>
    );
  }

  const items: StatItem[] = [
    {
      label: "集中",
      value: stats.focused_minutes,
      color: "text-green-400",
      bgColor: "bg-green-500/10",
    },
    {
      label: "散漫",
      value: stats.distracted_minutes,
      color: "text-yellow-400",
      bgColor: "bg-yellow-500/10",
    },
    {
      label: "眠気",
      value: stats.drowsy_minutes,
      color: "text-red-400",
      bgColor: "bg-red-500/10",
    },
    {
      label: "離席",
      value: stats.away_minutes,
      color: "text-gray-400",
      bgColor: "bg-gray-500/10",
    },
  ];

  const totalMinutes =
    stats.focused_minutes +
    stats.distracted_minutes +
    stats.drowsy_minutes +
    stats.away_minutes;

  return (
    <div>
      <div className="grid grid-cols-2 gap-3">
        {items.map((item) => (
          <div
            key={item.label}
            className={`rounded-lg p-3 ${item.bgColor}`}
          >
            <div className={`text-2xl font-bold ${item.color}`}>
              {formatMinutes(item.value)}
            </div>
            <div className="text-xs text-gray-500 mt-1">{item.label}</div>
            {totalMinutes > 0 && (
              <div className="text-xs text-gray-600 mt-0.5">
                {Math.round((item.value / totalMinutes) * 100)}%
              </div>
            )}
          </div>
        ))}
      </div>

      {stats.notification_count > 0 && (
        <div className="mt-3 text-xs text-gray-500 text-center">
          今日の通知: {stats.notification_count}回
        </div>
      )}
    </div>
  );
}
