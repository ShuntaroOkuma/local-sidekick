import { useState, useRef } from "react";
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

const BUCKET_MINUTES = 5;
const PX_PER_HOUR = 60;
const MAX_ENTRY_DURATION_SEC = 30;

const STATE_COLORS: Record<string, { bg: string; text: string }> = {
  focused: { bg: "bg-green-500/15", text: "text-green-400" },
  drowsy: { bg: "bg-red-500/15", text: "text-red-400" },
  distracted: { bg: "bg-yellow-500/15", text: "text-yellow-400" },
  away: { bg: "bg-gray-600/15", text: "text-gray-500" },
};

const STATE_BORDER_COLORS: Record<string, string> = {
  focused: "#22c55e",
  drowsy: "#ef4444",
  distracted: "#eab308",
  away: "#4b5563",
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

const FALLBACK_COLOR = { bg: "bg-gray-500/15", text: "text-gray-500" };

/** State → total seconds within a segment */
type StateBreakdown = Record<string, number>;

interface Segment {
  state: string;
  startTime: Date;
  endTime: Date;
  durationMin: number;
  breakdown: StateBreakdown;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}分`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}時間${m}分` : `${h}時間`;
}

function formatSeconds(sec: number): string {
  if (sec < 60) return `${Math.round(sec)}秒`;
  const m = Math.round(sec / 60);
  return `${m}分`;
}

/** Merge two breakdowns by summing durations per state */
function mergeBreakdowns(a: StateBreakdown, b: StateBreakdown): StateBreakdown {
  const result = { ...a };
  for (const [state, dur] of Object.entries(b)) {
    result[state] = (result[state] ?? 0) + dur;
  }
  return result;
}

/**
 * Bucket history entries into 5-minute windows, pick the dominant state
 * per window (majority vote by duration), then merge consecutive
 * same-state buckets. Buckets with no data produce no segment (gap).
 * Each segment carries a breakdown of actual seconds per state.
 */
function buildSegments(history: HistoryEntry[]): Segment[] {
  if (history.length === 0) return [];

  const sorted = [...history].sort((a, b) => a.timestamp - b.timestamp);

  // Step 1: Assign each entry to a 5-min bucket, weighted by duration
  const buckets = new Map<number, Map<string, number>>();

  for (let i = 0; i < sorted.length; i++) {
    const entry = sorted[i];
    const entryDate = new Date(entry.timestamp * 1000);

    const bucketMinute =
      Math.floor(entryDate.getMinutes() / BUCKET_MINUTES) * BUCKET_MINUTES;
    const bucketStart = new Date(entryDate);
    bucketStart.setMinutes(bucketMinute, 0, 0);
    const bucketKey = Math.floor(bucketStart.getTime() / 1000);

    const nextTs =
      i + 1 < sorted.length ? sorted[i + 1].timestamp : entry.timestamp + 5;
    const duration = Math.min(
      nextTs - entry.timestamp,
      MAX_ENTRY_DURATION_SEC
    );

    if (!buckets.has(bucketKey)) {
      buckets.set(bucketKey, new Map());
    }
    const stateMap = buckets.get(bucketKey)!;
    stateMap.set(
      entry.integrated_state,
      (stateMap.get(entry.integrated_state) ?? 0) + duration
    );
  }

  // Step 2: Pick dominant state per bucket, keep full breakdown
  const bucketResults: {
    bucketStart: number;
    state: string;
    breakdown: StateBreakdown;
  }[] = [];
  for (const [bucketStart, stateMap] of [...buckets.entries()].sort(
    (a, b) => a[0] - b[0]
  )) {
    let maxState = "";
    let maxDuration = 0;
    const breakdown: StateBreakdown = {};
    for (const [state, dur] of stateMap) {
      breakdown[state] = dur;
      if (dur > maxDuration) {
        maxState = state;
        maxDuration = dur;
      }
    }
    bucketResults.push({ bucketStart, state: maxState, breakdown });
  }

  // Step 3: Merge consecutive same-state buckets
  const segments: Segment[] = [];
  for (const bucket of bucketResults) {
    const startTime = new Date(bucket.bucketStart * 1000);
    const endTime = new Date(
      (bucket.bucketStart + BUCKET_MINUTES * 60) * 1000
    );

    if (segments.length > 0) {
      const last = segments[segments.length - 1];
      if (
        last.state === bucket.state &&
        Math.abs(last.endTime.getTime() - startTime.getTime()) < 1000
      ) {
        segments[segments.length - 1] = {
          ...last,
          endTime,
          durationMin: Math.round(
            (endTime.getTime() - last.startTime.getTime()) / 60000
          ),
          breakdown: mergeBreakdowns(last.breakdown, bucket.breakdown),
        };
        continue;
      }
    }

    segments.push({
      state: bucket.state,
      startTime,
      endTime,
      durationMin: BUCKET_MINUTES,
      breakdown: { ...bucket.breakdown },
    });
  }

  return segments;
}

/** Floating tooltip for segment hover, positioned at mouse cursor */
function SegmentTooltip({
  segment,
  mouseX,
  mouseY,
  containerRect,
}: {
  segment: Segment;
  mouseX: number;
  mouseY: number;
  containerRect: DOMRect;
}) {
  const colors = STATE_COLORS[segment.state] ?? FALLBACK_COLOR;

  const entries = Object.entries(segment.breakdown).sort(
    (a, b) => b[1] - a[1]
  );
  const totalSec = entries.reduce((sum, [, dur]) => sum + dur, 0);

  // Position relative to container, offset from mouse cursor
  const left = mouseX - containerRect.left + 12;
  const top = mouseY - containerRect.top;

  return (
    <div
      className="absolute z-50 pointer-events-none"
      style={{
        left,
        top,
        transform: "translateY(-50%)",
      }}
    >
      <div className="bg-gray-900/95 border border-gray-700 rounded-lg shadow-xl px-3 py-2 backdrop-blur-sm min-w-[160px]">
        {/* Header: time range → dominant state */}
        <div className="flex items-center gap-2 mb-1.5">
          <span className={`text-xs font-semibold ${colors.text}`}>
            {STATE_LABELS[segment.state] ?? segment.state}
          </span>
          <span className="text-[10px] text-gray-500">
            {formatTime(segment.startTime)} - {formatTime(segment.endTime)}
          </span>
        </div>

        {/* Breakdown bars */}
        <div className="space-y-1">
          {entries.map(([state, sec]) => {
            const pct = totalSec > 0 ? (sec / totalSec) * 100 : 0;
            const barColor = STATE_BORDER_COLORS[state] ?? "#6b7280";
            const isWinner = state === segment.state;
            return (
              <div key={state} className="flex items-center gap-2">
                <span
                  className={`text-[10px] w-8 text-right ${isWinner ? "text-gray-300" : "text-gray-500"}`}
                >
                  {STATE_LABELS[state] ?? state}
                </span>
                <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: barColor,
                      opacity: isWinner ? 1 : 0.4,
                    }}
                  />
                </div>
                <span className="text-[10px] text-gray-600 w-8">
                  {formatSeconds(sec)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function TimelineChart({
  history,
  notifications = [],
  startHour = 0,
  endHour = 24,
}: TimelineChartProps) {
  const totalMinutes = (endHour - startHour) * 60;
  const barHeight = (endHour - startHour) * PX_PER_HOUR;
  const hourLabels = Array.from(
    { length: endHour - startHour + 1 },
    (_, i) => startHour + i
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredSeg, setHoveredSeg] = useState<{
    segment: Segment;
    mouseX: number;
    mouseY: number;
  } | null>(null);

  function getPositionPct(timestamp: number): number {
    const date = new Date(timestamp * 1000);
    const minutes =
      date.getHours() * 60 + date.getMinutes() - startHour * 60;
    return Math.max(0, Math.min(100, (minutes / totalMinutes) * 100));
  }

  const segments = buildSegments(history);

  const notifsByTime = notifications.map((n) => ({
    ...n,
    position: getPositionPct(n.timestamp),
    time: new Date(n.timestamp * 1000),
  }));

  function handleMouseMove(seg: Segment, e: React.MouseEvent<HTMLDivElement>) {
    setHoveredSeg({ segment: seg, mouseX: e.clientX, mouseY: e.clientY });
  }

  function handleMouseLeave() {
    setHoveredSeg(null);
  }

  return (
    <div className="w-full flex gap-1" ref={containerRef}>
      {/* Hour labels */}
      <div
        className="relative flex-shrink-0"
        style={{ width: 44, height: barHeight }}
      >
        {hourLabels.map((hour) => (
          <div
            key={hour}
            className="absolute left-0 w-full flex items-center"
            style={{
              top: `${((hour - startHour) / (endHour - startHour)) * 100}%`,
            }}
          >
            <span className="text-[10px] text-gray-600 w-full text-right pr-2 -translate-y-1/2">
              {String(hour).padStart(2, "0")}:00
            </span>
          </div>
        ))}
      </div>

      {/* Timeline blocks area */}
      <div className="relative flex-1" style={{ height: barHeight }}>
        {/* Horizontal grid lines */}
        {hourLabels.map((hour) => (
          <div
            key={hour}
            className="absolute left-0 w-full border-t border-gray-800/40"
            style={{
              top: `${((hour - startHour) / (endHour - startHour)) * 100}%`,
            }}
          />
        ))}

        {/* State blocks — height proportional to duration */}
        {segments.map((seg) => {
          const topPct = getPositionPct(
            Math.floor(seg.startTime.getTime() / 1000)
          );
          const bottomPct = getPositionPct(
            Math.floor(seg.endTime.getTime() / 1000)
          );
          const heightPct = bottomPct - topPct;
          const heightPx = (heightPct / 100) * barHeight;
          const borderColor = STATE_BORDER_COLORS[seg.state] ?? "#6b7280";
          const colors = STATE_COLORS[seg.state] ?? FALLBACK_COLOR;

          return (
            <div
              key={`${seg.state}-${seg.startTime.getTime()}`}
              className={`absolute left-0 right-0 rounded-md overflow-hidden ${colors.bg} cursor-pointer transition-opacity hover:opacity-100 opacity-80`}
              style={{
                top: `${topPct}%`,
                height: `${Math.max(heightPct, 0.2)}%`,
                borderLeft: `3px solid ${borderColor}`,
              }}
              onMouseMove={(e) => handleMouseMove(seg, e)}
              onMouseLeave={handleMouseLeave}
            >
              {heightPx >= 14 && (
                <div className="px-2 h-full flex items-center gap-2 overflow-hidden">
                  <span
                    className={`text-xs font-medium ${colors.text} whitespace-nowrap`}
                  >
                    {STATE_LABELS[seg.state] ?? seg.state}
                  </span>
                  <span className="text-[10px] text-gray-500 whitespace-nowrap">
                    {formatTime(seg.startTime)}-{formatTime(seg.endTime)}
                  </span>
                  {heightPx >= 28 && (
                    <span className="text-[10px] text-gray-600 ml-auto whitespace-nowrap">
                      {formatDuration(seg.durationMin)}
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {/* Notification markers */}
        {notifsByTime.map((notif) => (
          <div
            key={notif.id}
            className="absolute right-0 w-2.5 h-2.5 bg-white rounded-full border-2 border-gray-900 z-[1]"
            style={{ top: `${notif.position}%`, marginTop: -5 }}
            title={`${NOTIF_TYPE_LABELS[notif.type] ?? notif.type} - ${formatTime(notif.time)}${notif.user_action ? ` (${NOTIF_ACTION_LABELS[notif.user_action]})` : ""}`}
          />
        ))}

        {/* Hover tooltip */}
        {hoveredSeg && containerRef.current && (
          <SegmentTooltip
            segment={hoveredSeg.segment}
            mouseX={hoveredSeg.mouseX}
            mouseY={hoveredSeg.mouseY}
            containerRect={containerRef.current.getBoundingClientRect()}
          />
        )}
      </div>
    </div>
  );
}
