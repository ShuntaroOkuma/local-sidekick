import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import type { ModelInfo } from "../lib/types";

export function useModels() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchModels = useCallback(async () => {
    try {
      const data = await api.getModels();
      setModels(data);
      setError(null);
    } catch (err) {
      setError("モデル情報の取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  // Poll every 2s while any model is downloading
  useEffect(() => {
    const isDownloading = models.some((m) => m.downloading);
    if (!isDownloading) return;
    const interval = setInterval(fetchModels, 2000);
    return () => clearInterval(interval);
  }, [models, fetchModels]);

  const startDownload = useCallback(
    async (modelId: string) => {
      try {
        await api.downloadModel(modelId);
        setModels((prev) =>
          prev.map((m) =>
            m.id === modelId ? { ...m, downloading: true, error: null } : m
          )
        );
      } catch (err) {
        setModels((prev) =>
          prev.map((m) =>
            m.id === modelId
              ? { ...m, error: "ダウンロードの開始に失敗しました" }
              : m
          )
        );
      }
    },
    []
  );

  const removeModel = useCallback(
    async (modelId: string) => {
      try {
        await api.deleteModel(modelId);
        await fetchModels();
      } catch (err) {
        setModels((prev) =>
          prev.map((m) =>
            m.id === modelId
              ? { ...m, error: "モデルの削除に失敗しました" }
              : m
          )
        );
      }
    },
    [fetchModels]
  );

  return { models, loading, error, startDownload, removeModel, refetch: fetchModels };
}
