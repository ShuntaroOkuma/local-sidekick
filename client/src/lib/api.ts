import type {
  EngineState,
  HistoryEntry,
  DailyStats,
  Settings,
  NotificationEntry,
} from "./types";

const DEFAULT_BASE_URL = "http://localhost:18080";

let _baseUrl: string | null = null;

async function getBaseUrl(): Promise<string> {
  if (_baseUrl) return _baseUrl;
  try {
    _baseUrl = await (window as any).electronAPI?.getEngineUrl() ?? DEFAULT_BASE_URL;
  } catch {
    _baseUrl = DEFAULT_BASE_URL;
  }
  return _baseUrl;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const base = await getBaseUrl();
  const url = `${base}${path}`;
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export const api = {
  // Health check
  health: (): Promise<{ status: string }> => request("/api/health"),

  // Current state
  getState: (): Promise<EngineState> => request("/api/state"),

  // History
  getHistory: (date?: string): Promise<HistoryEntry[]> => {
    const params = date ? `?date=${date}` : "";
    return request(`/api/history${params}`);
  },

  // Daily stats
  getDailyStats: (date?: string): Promise<DailyStats> => {
    const params = date ? `?date=${date}` : "";
    return request(`/api/daily-stats${params}`);
  },

  // Notifications
  getNotifications: (date?: string): Promise<NotificationEntry[]> => {
    const params = date ? `?date=${date}` : "";
    return request(`/api/notifications${params}`);
  },

  // Settings
  getSettings: (): Promise<Settings> => request("/api/settings"),

  updateSettings: (settings: Partial<Settings>): Promise<Settings> =>
    request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),

  // Report generation
  generateReport: (date?: string): Promise<DailyStats> => {
    const params = date ? `?date=${date}` : "";
    return request(`/api/reports/generate${params}`, {
      method: "POST",
    });
  },

  // Engine control
  startEngine: (): Promise<{ status: string }> =>
    request("/api/engine/start", { method: "POST" }),

  stopEngine: (): Promise<{ status: string }> =>
    request("/api/engine/stop", { method: "POST" }),
};
