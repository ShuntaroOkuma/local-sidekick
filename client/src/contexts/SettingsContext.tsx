import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { api } from "../lib/api";
import type { Settings } from "../lib/types";

const DEFAULT_SETTINGS: Settings = {
  working_hours_start: "09:00",
  working_hours_end: "19:00",
  max_notifications_per_day: 6,
  camera_enabled: true,
  model_tier: "lightweight",
  sync_enabled: true,
  avatar_enabled: true,
};

interface SettingsContextValue {
  settings: Settings;
  loading: boolean;
  error: string | null;
  updateSettings: (updates: Partial<Settings>) => Promise<boolean>;
  refetch: () => Promise<void>;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch (err) {
      console.error("Failed to fetch settings:", err);
      setError("設定の取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, []);

  const updateSettings = useCallback(
    async (updates: Partial<Settings>) => {
      setError(null);
      try {
        const updated = await api.updateSettings(updates);
        setSettings(updated);
        return true;
      } catch (err) {
        console.error("Failed to update settings:", err);
        setError("設定の保存に失敗しました");
        return false;
      }
    },
    []
  );

  useEffect(() => {
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout>;

    async function fetchWithRetry(attempt: number) {
      try {
        const data = await api.getSettings();
        if (!cancelled) {
          setSettings(data);
          setError(null);
          setLoading(false);
        }
      } catch {
        if (!cancelled && attempt < 5) {
          // Engine may still be starting — retry with backoff
          retryTimer = setTimeout(() => fetchWithRetry(attempt + 1), 2000 * attempt);
        } else if (!cancelled) {
          setError("設定の取得に失敗しました");
          setLoading(false);
        }
      }
    }

    fetchWithRetry(1);
    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
    };
  }, []);

  return (
    <SettingsContext.Provider
      value={{ settings, loading, error, updateSettings, refetch: fetchSettings }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettingsContext(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) {
    throw new Error("useSettingsContext must be used within a SettingsProvider");
  }
  return ctx;
}
