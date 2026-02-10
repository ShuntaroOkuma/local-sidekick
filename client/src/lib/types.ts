export type UserState = "focused" | "drowsy" | "distracted" | "away" | "idle";
export type NotificationType = "drowsy" | "distracted" | "over_focus";
export type NotificationAction = "accepted" | "snoozed" | "dismissed";

export interface EngineState {
  state: UserState;
  confidence: number;
  camera_state: UserState;
  pc_state: string;
  timestamp: number;
}

export interface HistoryEntry {
  timestamp: number;
  integrated_state: UserState;
  camera_state: string;
  pc_state: string;
  confidence: number;
}

export interface NotificationEntry {
  id: number;
  timestamp: number;
  type: NotificationType;
  message: string;
  user_action: NotificationAction | null;
}

export interface DailyStats {
  focused_minutes: number;
  drowsy_minutes: number;
  distracted_minutes: number;
  away_minutes: number;
  idle_minutes: number;
  notification_count: number;
  report?: DailyReport;
}

export interface DailyReport {
  summary: string;
  highlights: string[];
  concerns: string[];
  tomorrow_tip: string;
}

export interface Settings {
  working_hours_start: string;
  working_hours_end: string;
  max_notifications_per_day: number;
  camera_enabled: boolean;
  sync_enabled: boolean;
}

export interface ElectronAPI {
  getEngineUrl: () => Promise<string>;
  onNotification: (callback: (data: { type: string; message: string }) => void) => void;
  sendNotificationResponse: (type: string, action: string) => void;
  getAppVersion: () => Promise<string>;
  getPlatform: () => Promise<string>;
  onNavigate: (callback: (path: string) => void) => void;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
