import type { NotificationEntry } from "../lib/types";

interface NotificationCardProps {
  notification: NotificationEntry;
}

const TYPE_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  drowsy: { label: "眠気", icon: "😴", color: "text-red-400" },
  distracted: { label: "散漫", icon: "🔀", color: "text-yellow-400" },
  over_focus: { label: "過集中", icon: "🔥", color: "text-orange-400" },
};

const ACTION_LABELS: Record<string, string> = {
  accepted: "✓ 実行",
  snoozed: "⏰ あとで",
  dismissed: "✕ 閉じた",
};

export function NotificationCard({ notification }: NotificationCardProps) {
  const config = TYPE_CONFIG[notification.type] || {
    label: notification.type,
    icon: "🔔",
    color: "text-gray-400",
  };

  const time = new Date(notification.timestamp * 1000).toLocaleTimeString(
    "ja-JP",
    { hour: "2-digit", minute: "2-digit" }
  );

  return (
    <div className="flex items-center gap-3 p-3 bg-gray-800 rounded-lg">
      <span className="text-xl">{config.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${config.color}`}>
            {config.label}
          </span>
          <span className="text-xs text-gray-500">{time}</span>
        </div>
        {notification.message && (
          <p className="text-xs text-gray-400 truncate">{notification.message}</p>
        )}
      </div>
      {notification.user_action && (
        <span className="text-xs text-gray-500">
          {ACTION_LABELS[notification.user_action] || notification.user_action}
        </span>
      )}
    </div>
  );
}
