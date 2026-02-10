import type { HistoryEntry, UserState, NotificationEntry } from "../lib/types";

interface TimelineChartProps {
  history: HistoryEntry[];
  notifications?: NotificationEntry[];
  startHour?: number;
  endHour?: number;
}

const STATE_COLORS: Record<UserState, string> = {
  focused: "bg-green-500",
  drowsy: "bg-red-500",
  distracted: "bg-yellow-500",
  away: "bg-gray-600",
  idle: "bg-gray-500",
};

const STATE_LABELS: Record<UserState, string> = {
  focused: "集中",
  drowsy: "眠気",
  distracted: "散漫",
  away: "離席",
  idle: "待機",
};

export function TimelineChart({
  history,
  notifications = [],
  startHour = 9,
  endHour = 19,
}: TimelineChartProps) {
  const totalMinutes = (endHour - startHour) * 60;
  const hourLabels = Array.from(
    { length: endHour - startHour + 1 },
    (_, i) => startHour + i
  );

  function getPosition(timestamp: number): number {
    const date = new Date(timestamp * 1000);
    const minutes = date.getHours() * 60 + date.getMinutes() - startHour * 60;
    return Math.max(0, Math.min(100, (minutes / totalMinutes) * 100));
  }

  // Group consecutive same-state entries into segments
  const segments: { state: UserState; startPct: number; endPct: number }[] = [];
  for (let i = 0; i < history.length; i++) {
    const entry = history[i];
    const startPct = getPosition(entry.timestamp);
    const endPct =
      i + 1 < history.length
        ? getPosition(history[i + 1].timestamp)
        : startPct + (5 / totalMinutes) * 100; // 5 min default width

    if (
      segments.length > 0 &&
      segments[segments.length - 1].state === entry.integrated_state &&
      Math.abs(segments[segments.length - 1].endPct - startPct) < 1
    ) {
      segments[segments.length - 1].endPct = endPct;
    } else {
      segments.push({
        state: entry.integrated_state,
        startPct,
        endPct: Math.min(endPct, 100),
      });
    }
  }

  return (
    <div className="w-full">
      {/* Timeline bar */}
      <div className="relative w-full h-10 bg-gray-800 rounded-lg overflow-hidden">
        {segments.map((seg, i) => (
          <div
            key={i}
            className={`absolute top-0 h-full ${STATE_COLORS[seg.state]} opacity-80`}
            style={{
              left: `${seg.startPct}%`,
              width: `${Math.max(seg.endPct - seg.startPct, 0.5)}%`,
            }}
            title={STATE_LABELS[seg.state]}
          />
        ))}
        {/* Notification markers */}
        {notifications.map((notif, i) => (
          <div
            key={`notif-${i}`}
            className="absolute top-0 h-full w-0.5 bg-white/60"
            style={{ left: `${getPosition(notif.timestamp)}%` }}
            title={`通知: ${notif.type}`}
          >
            <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-white rounded-full" />
          </div>
        ))}
      </div>

      {/* Hour labels */}
      <div className="relative w-full mt-1">
        {hourLabels.map((hour) => (
          <span
            key={hour}
            className="absolute text-xs text-gray-500 -translate-x-1/2"
            style={{
              left: `${((hour - startHour) / (endHour - startHour)) * 100}%`,
            }}
          >
            {hour}:00
          </span>
        ))}
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-6 justify-center">
        {(Object.keys(STATE_COLORS) as UserState[]).map((state) => (
          <div key={state} className="flex items-center gap-1">
            <div className={`w-3 h-3 rounded-sm ${STATE_COLORS[state]}`} />
            <span className="text-xs text-gray-400">{STATE_LABELS[state]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
