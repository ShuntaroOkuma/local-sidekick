import type {
  HistoryEntry,
  NotificationEntry,
  NotificationAction,
} from "../lib/types";

interface TimelineChartProps {
  history: HistoryEntry[];
  notifications?: NotificationEntry[];
  startHour?: number;
  endHour?: number;
}

const FALLBACK_COLOR = { bg: "bg-gray-500/20", text: "text-gray-500" };
const FALLBACK_DOT = "bg-gray-500";

const STATE_COLORS: Record<string, { bg: string; text: string }> = {
  focused: { bg: "bg-green-500/20", text: "text-green-400" },
  drowsy: { bg: "bg-red-500/20", text: "text-red-400" },
  distracted: { bg: "bg-yellow-500/20", text: "text-yellow-400" },
  away: { bg: "bg-gray-600/20", text: "text-gray-500" },
};

const STATE_DOT_COLORS: Record<string, string> = {
  focused: "bg-green-500",
  drowsy: "bg-red-500",
  distracted: "bg-yellow-500",
  away: "bg-gray-600",
};

const STATE_LABELS: Record<string, string> = {
  focused: "集中",
  drowsy: "眠気",
  distracted: "散漫",
  away: "離席",
  unknown: "不明",
};

const NOTIF_TYPE_LABELS: Record<string, string> = {
  drowsy: "眠気検知",
  distracted: "散漫検知",
  over_focus: "過集中",
};

const NOTIF_ACTION_LABELS: Record<NotificationAction, string> = {
  accepted: "対応済み",
  snoozed: "スヌーズ",
  dismissed: "無視",
};

interface Segment {
  state: string;
  startTime: Date;
  endTime: Date;
  durationMin: number;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

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

  // Sort ASC (API returns DESC) then group consecutive same-state entries
  const sorted = [...history].sort((a, b) => a.timestamp - b.timestamp);
  const segments: Segment[] = [];
  for (let i = 0; i < sorted.length; i++) {
    const entry = sorted[i];
    const nextTimestamp =
      i + 1 < sorted.length
        ? sorted[i + 1].timestamp
        : entry.timestamp + 300;

    const startTime = new Date(entry.timestamp * 1000);
    const endTime = new Date(nextTimestamp * 1000);
    const durationMin = Math.round(
      (endTime.getTime() - startTime.getTime()) / 60000
    );

    if (
      segments.length > 0 &&
      segments[segments.length - 1].state === entry.integrated_state
    ) {
      const last = segments[segments.length - 1];
      segments[segments.length - 1] = {
        ...last,
        endTime,
        durationMin: Math.round(
          (endTime.getTime() - last.startTime.getTime()) / 60000
        ),
      };
    } else {
      segments.push({
        state: entry.integrated_state,
        startTime,
        endTime,
        durationMin,
      });
    }
  }

  // Index notifications by timestamp for overlay
  const notifsByTime = notifications.map((n) => ({
    ...n,
    position: getPosition(n.timestamp),
    time: new Date(n.timestamp * 1000),
  }));

  const barHeight = (endHour - startHour) * 40;

  return (
    <div className="w-full flex gap-4">
      {/* Vertical timeline bar */}
      <div
        className="relative flex-shrink-0"
        style={{ width: 40, height: barHeight }}
      >
        {/* Hour markers */}
        {hourLabels.map((hour) => (
          <div
            key={hour}
            className="absolute left-0 w-full flex items-center"
            style={{
              top: `${((hour - startHour) / (endHour - startHour)) * 100}%`,
            }}
          >
            <span className="text-[10px] text-gray-600 w-full text-right pr-1 -translate-y-1/2">
              {hour}:00
            </span>
          </div>
        ))}
      </div>

      {/* Bar + segments */}
      <div
        className="relative flex-shrink-0"
        style={{ width: 12, height: barHeight }}
      >
        <div className="absolute inset-0 bg-gray-800 rounded-full" />
        {/* State segments on the bar */}
        {segments.map((seg, i) => {
          const topPct = getPosition(
            Math.floor(seg.startTime.getTime() / 1000)
          );
          const bottomPct = getPosition(
            Math.floor(seg.endTime.getTime() / 1000)
          );
          return (
            <div
              key={`${seg.state}-${seg.startTime.getTime()}`}
              className={`absolute left-0 w-full ${STATE_DOT_COLORS[seg.state] ?? FALLBACK_DOT} opacity-80 ${
                i === 0 ? "rounded-t-full" : ""
              } ${i === segments.length - 1 ? "rounded-b-full" : ""}`}
              style={{
                top: `${topPct}%`,
                height: `${Math.max(bottomPct - topPct, 0.5)}%`,
              }}
            />
          );
        })}
        {/* Notification markers */}
        {notifsByTime.map((notif) => (
          <div
            key={notif.id}
            className="absolute left-1/2 -translate-x-1/2 w-3 h-3 bg-white rounded-full border-2 border-gray-900 z-[1]"
            style={{ top: `${notif.position}%`, marginTop: -6 }}
          />
        ))}
      </div>

      {/* Segment detail list */}
      <div className="flex-1 min-w-0 space-y-1">
        {segments.map((seg) => (
          <div
            key={`${seg.state}-${seg.startTime.getTime()}`}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg ${(STATE_COLORS[seg.state] ?? FALLBACK_COLOR).bg}`}
          >
            <div
              className={`w-2 h-2 rounded-full flex-shrink-0 ${STATE_DOT_COLORS[seg.state] ?? FALLBACK_DOT}`}
            />
            <span
              className={`text-sm font-medium ${(STATE_COLORS[seg.state] ?? FALLBACK_COLOR).text} w-10`}
            >
              {STATE_LABELS[seg.state] ?? seg.state}
            </span>
            <span className="text-xs text-gray-500 font-mono">
              {formatTime(seg.startTime)} - {formatTime(seg.endTime)}
            </span>
            <span className="text-xs text-gray-600 ml-auto">
              {seg.durationMin}分
            </span>
          </div>
        ))}

        {/* Notification entries inline */}
        {notifsByTime.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-800 space-y-1">
            {notifsByTime.map((notif) => {
              const typeLabel =
                NOTIF_TYPE_LABELS[notif.type] ?? notif.type;
              const actionLabel = notif.user_action
                ? NOTIF_ACTION_LABELS[notif.user_action]
                : "未対応";
              return (
                <div
                  key={notif.id}
                  className="flex items-center gap-3 px-3 py-1.5 rounded-lg bg-white/5"
                >
                  <div className="w-2 h-2 rounded-full flex-shrink-0 bg-white" />
                  <span className="text-xs text-gray-300">{typeLabel}</span>
                  <span className="text-xs text-gray-500 font-mono">
                    {formatTime(notif.time)}
                  </span>
                  <span className="text-xs text-gray-600 ml-auto">
                    {actionLabel}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
