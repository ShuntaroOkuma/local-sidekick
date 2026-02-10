import type { UserState } from "../lib/types";

interface StateIndicatorProps {
  state: UserState | null;
  confidence?: number;
  size?: "sm" | "md" | "lg";
}

const STATE_CONFIG: Record<
  UserState,
  { label: string; emoji: string; color: string; bgColor: string }
> = {
  focused: {
    label: "集中",
    emoji: "🟢",
    color: "text-green-400",
    bgColor: "bg-green-500/20",
  },
  drowsy: {
    label: "眠気",
    emoji: "🔴",
    color: "text-red-400",
    bgColor: "bg-red-500/20",
  },
  distracted: {
    label: "散漫",
    emoji: "🟡",
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/20",
  },
  away: {
    label: "離席",
    emoji: "⚪",
    color: "text-gray-400",
    bgColor: "bg-gray-500/20",
  },
  idle: {
    label: "待機",
    emoji: "⚪",
    color: "text-gray-500",
    bgColor: "bg-gray-500/20",
  },
};

const SIZE_CLASSES = {
  sm: { container: "p-3", emoji: "text-2xl", label: "text-sm" },
  md: { container: "p-4", emoji: "text-4xl", label: "text-lg" },
  lg: { container: "p-6", emoji: "text-6xl", label: "text-2xl" },
};

export function StateIndicator({
  state,
  confidence,
  size = "lg",
}: StateIndicatorProps) {
  if (!state) {
    return (
      <div className="flex flex-col items-center gap-2 p-6">
        <span className="text-6xl animate-pulse">⭕</span>
        <span className="text-gray-500 text-lg">接続待ち...</span>
      </div>
    );
  }

  const config = STATE_CONFIG[state];
  const sizeClass = SIZE_CLASSES[size];

  return (
    <div
      className={`flex flex-col items-center gap-2 rounded-2xl ${config.bgColor} ${sizeClass.container}`}
    >
      <span className={sizeClass.emoji}>{config.emoji}</span>
      <span className={`font-bold ${config.color} ${sizeClass.label}`}>
        {config.label}
      </span>
      {confidence !== undefined && (
        <div className="w-full max-w-32">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>信頼度</span>
            <span>{Math.round(confidence * 100)}%</span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full transition-all duration-500 ${
                confidence > 0.8
                  ? "bg-green-500"
                  : confidence > 0.5
                    ? "bg-yellow-500"
                    : "bg-red-500"
              }`}
              style={{ width: `${confidence * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
