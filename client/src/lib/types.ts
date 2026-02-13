export type UserState = "focused" | "drowsy" | "distracted" | "away";
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
  notification_count: number;
  report?: DailyReport;
}

export interface DailyReport {
  summary: string;
  highlights: string[];
  concerns: string[];
  tomorrow_tip: string;
  report_source?: "local" | "cloud";
}

export type ModelTier = "none" | "lightweight" | "recommended";

export interface ModelInfo {
  id: string;
  name: string;
  description: string;
  size_gb: number;
  tier: string;
  downloaded: boolean;
  downloading: boolean;
  error: string | null;
}

export interface Settings {
  working_hours_start: string;
  working_hours_end: string;
  camera_enabled: boolean;
  model_tier: ModelTier;
  sync_enabled: boolean;
  avatar_enabled: boolean;
  cloud_run_url?: string;
  cloud_auth_email?: string;
}

export interface CloudAuthRequest {
  email: string;
  password: string;
}

export interface CloudAuthResponse {
  status: string;
  email: string;
}

export interface ElectronAPI {
  getEngineUrl: () => Promise<string>;
  onNotification: (callback: (data: { type: string; message: string }) => void) => () => void;
  sendNotificationResponse: (type: string, action: string) => void;
  getAppVersion: () => Promise<string>;
  getPlatform: () => Promise<string>;
  onNavigate: (callback: (path: string) => void) => () => void;
  getAvatarEnabled: () => Promise<boolean>;
  setAvatarEnabled: (enabled: boolean) => Promise<void>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
