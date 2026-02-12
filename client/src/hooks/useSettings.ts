import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import type { Settings } from "../lib/types";

const DEFAULT_SETTINGS: Settings = {
  working_hours_start: "09:00",
  working_hours_end: "19:00",
  max_notifications_per_day: 6,
  camera_enabled: true,
  model_tier: "lightweight",
  sync_enabled: true,
};

export function useSettings() {
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
    fetchSettings();
  }, [fetchSettings]);

  return { settings, loading, error, updateSettings, refetch: fetchSettings };
}
