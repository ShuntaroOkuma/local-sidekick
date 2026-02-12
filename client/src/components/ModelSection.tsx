import { useEffect } from "react";
import { useModels } from "../hooks/useModels";
import { ModelCard } from "./ModelCard";
import type { ModelTier } from "../lib/types";

interface ModelSectionProps {
  currentTier: ModelTier;
  onTierChange: (tier: ModelTier) => void;
}

const TIER_OPTIONS: { value: ModelTier; label: string }[] = [
  { value: "none", label: "無効" },
  { value: "lightweight", label: "軽量 (3B)" },
  { value: "recommended", label: "推奨 (7B)" },
];

const TIER_DESCRIPTIONS: Record<ModelTier, string> = {
  none: "LLMを使用せず、ルールベースのみで判定します。モデルのダウンロードは不要です。",
  lightweight:
    "3Bモデルで高速に判定。ルールで判定できない場合のフォールバックとして使用。",
  recommended:
    "7Bモデルでより正確に判定。メモリ使用量が多くなります。",
};

const TIER_TO_MODEL_ID: Record<string, string> = {
  lightweight: "qwen2.5-3b",
  recommended: "qwen2.5-7b",
};

export function ModelSection({ currentTier, onTierChange }: ModelSectionProps) {
  const { models, loading, error, startDownload, removeModel } = useModels();

  const selectedModelId = TIER_TO_MODEL_ID[currentTier];
  const selectedModel = models.find((m) => m.id === selectedModelId);
  const needsDownload =
    currentTier !== "none" && selectedModel && !selectedModel.downloaded;

  // Auto-switch to "none" when selected model is not downloaded
  useEffect(() => {
    if (loading || models.length === 0) return;
    if (currentTier === "none") return;
    const requiredModel = models.find((m) => m.id === TIER_TO_MODEL_ID[currentTier]);
    if (requiredModel && !requiredModel.downloaded && !requiredModel.downloading) {
      onTierChange("none");
    }
  }, [models, loading, currentTier, onTierChange]);

  return (
    <div className="bg-gray-800/50 rounded-xl p-5 space-y-4">
      <h2 className="text-sm font-semibold text-gray-300">AIモデル設定</h2>

      {/* Tier selector */}
      <div className="flex rounded-lg overflow-hidden border border-gray-700">
        {TIER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onTierChange(opt.value)}
            className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
              currentTier === opt.value
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Description */}
      <p className="text-xs text-gray-500">{TIER_DESCRIPTIONS[currentTier]}</p>

      {/* Warning if selected model not downloaded */}
      {needsDownload && (
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3">
          <p className="text-xs text-yellow-400">
            選択中のモデルがダウンロードされていません。下のボタンからダウンロードしてください。
          </p>
        </div>
      )}

      {/* Note about engine restart */}
      {currentTier !== "none" && (
        <p className="text-xs text-gray-600">
          ※ モデル変更はエンジンの再起動後に反映されます
        </p>
      )}

      {/* Model cards */}
      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}

      {loading ? (
        <div className="space-y-2">
          <div className="bg-gray-900/50 rounded-lg h-14 animate-pulse" />
          <div className="bg-gray-900/50 rounded-lg h-14 animate-pulse" />
        </div>
      ) : (
        <div className="space-y-2">
          {models
            .filter((model) => model.tier !== "vision")
            .map((model) => (
              <ModelCard
                key={model.id}
                model={model}
                onDownload={startDownload}
                onDelete={removeModel}
              />
            ))}
        </div>
      )}
    </div>
  );
}
