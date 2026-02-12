import type { ModelInfo } from "../lib/types";

interface ModelCardProps {
  model: ModelInfo;
  onDownload: (modelId: string) => void;
  onDelete: (modelId: string) => void;
}

export function ModelCard({ model, onDownload, onDelete }: ModelCardProps) {
  return (
    <div className="flex items-center justify-between bg-gray-900/50 rounded-lg p-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">
            {model.name}
          </span>
          <span className="text-xs text-gray-500">
            {model.size_gb < 0.01
              ? `${(model.size_gb * 1024).toFixed(0)}MB`
              : `${model.size_gb}GB`}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-0.5">{model.description}</p>
        {model.error && (
          <p className="text-xs text-red-400 mt-1">{model.error}</p>
        )}
      </div>

      <div className="flex items-center gap-2 ml-3 shrink-0">
        {model.downloading ? (
          <span className="flex items-center gap-1.5 text-xs text-blue-400">
            <svg
              className="w-3.5 h-3.5 animate-spin"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            DL中...
          </span>
        ) : model.downloaded ? (
          <>
            <span className="text-xs text-green-400">DL済み</span>
            <button
              onClick={() => onDelete(model.id)}
              className="text-xs text-gray-500 hover:text-red-400 transition-colors"
            >
              削除
            </button>
          </>
        ) : (
          <button
            onClick={() => onDownload(model.id)}
            className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded transition-colors"
          >
            DL
          </button>
        )}
      </div>
    </div>
  );
}
