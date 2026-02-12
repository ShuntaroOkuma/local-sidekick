import { Notification } from "electron";

let avatarEnabled = false;

export function setAvatarEnabled(enabled: boolean): void {
  avatarEnabled = enabled;
}

export function isAvatarEnabled(): boolean {
  return avatarEnabled;
}

export type NotificationType = "drowsy" | "distracted" | "over_focus";

interface NotificationConfig {
  title: string;
  body: string;
}

const NOTIFICATION_CONFIGS: Record<NotificationType, NotificationConfig> = {
  drowsy: {
    title: "眠気が来ています",
    body: "90秒立ちましょう",
  },
  distracted: {
    title: "集中が途切れています",
    body: "10分だけ1タスクに戻りませんか？",
  },
  over_focus: {
    title: "集中しすぎです",
    body: "2分休憩で効率維持しませんか？",
  },
};

export function showNotification(
  type: NotificationType,
  onAction?: (action: string) => void
): void {
  // When avatar mode is active, skip OS notifications;
  // the avatar window handles them via WebSocket/IPC instead.
  if (avatarEnabled) return;

  const config = NOTIFICATION_CONFIGS[type];
  if (!config) return;

  const notification = new Notification({
    title: config.title,
    body: config.body,
    silent: false,
    actions: [
      { type: "button", text: "実行" },
      { type: "button", text: "あとで" },
    ],
  });

  notification.on("action", (_event, index) => {
    const action = index === 0 ? "accepted" : "snoozed";
    onAction?.(action);
  });

  notification.on("click", () => {
    onAction?.("accepted");
  });

  notification.on("close", () => {
    onAction?.("dismissed");
  });

  notification.show();
}
