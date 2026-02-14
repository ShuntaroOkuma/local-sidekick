import type {
  EngineState,
  HistoryEntry,
  BucketedSegment,
  TimeRange,
  DailyStats,
  DailyReport,
  Settings,
  NotificationEntry,
  ModelInfo,
  CloudAuthResponse,
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
  return _baseUrl ?? DEFAULT_BASE_URL;
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

  // History (API accepts start/end as Unix timestamps)
  getHistory: async (range?: TimeRange): Promise<HistoryEntry[]> => {
    const params = range
      ? `?start=${range.start}&end=${range.end}`
      : "";
    const res = await request<{ state_log: HistoryEntry[] }>(
      `/api/history${params}`
    );
    return res.state_log ?? [];
  },

  // Bucketed history (API returns pre-aggregated segments)
  getHistoryBucketed: async (range: TimeRange): Promise<BucketedSegment[]> => {
    const res = await request<{ segments: BucketedSegment[] }>(
      `/api/history/bucketed?start=${range.start}&end=${range.end}`
    );
    return res.segments ?? [];
  },

  // Daily stats (accepts YYYY-MM-DD date string)
  getDailyStats: (date?: string): Promise<DailyStats> => {
    const params = date ? `?date=${date}` : "";
    return request(`/api/daily-stats${params}`);
  },

  // Notifications (API accepts start/end as Unix timestamps)
  getNotifications: async (range?: TimeRange): Promise<NotificationEntry[]> => {
    const params = range
      ? `?start=${range.start}&end=${range.end}`
      : "";
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

  // Report retrieval (past reports)
  getReport: (date: string): Promise<DailyReport> =>
    request(`/api/reports/${date}`),

  listReports: async (): Promise<string[]> => {
    const res = await request<{ dates: string[] }>("/api/reports");
    return res.dates ?? [];
  },

  // Engine control
  startEngine: (): Promise<{ status: string }> =>
    request("/api/engine/start", { method: "POST" }),

  stopEngine: (): Promise<{ status: string }> =>
    request("/api/engine/stop", { method: "POST" }),

  // Model management
  getModels: (): Promise<ModelInfo[]> => request("/api/models"),

  downloadModel: (modelId: string): Promise<{ status: string; message: string }> =>
    request(`/api/models/${modelId}/download`, { method: "POST" }),

  deleteModel: (modelId: string): Promise<{ status: string; message: string }> =>
    request(`/api/models/${modelId}`, { method: "DELETE" }),

  // Cloud URL check
  cloudCheckUrl: (url: string): Promise<{ status: string }> =>
    request("/api/cloud/check-url", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  // Cloud authentication
  cloudLogin: (email: string, password: string): Promise<CloudAuthResponse> =>
    request("/api/cloud/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  cloudRegister: (email: string, password: string): Promise<CloudAuthResponse> =>
    request("/api/cloud/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  cloudLogout: (): Promise<void> =>
    request("/api/cloud/logout", { method: "POST" }),
};
