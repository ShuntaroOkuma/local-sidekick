import { useModels } from "../hooks/useModels";
import { ModelCard } from "./ModelCard";

interface CameraSectionProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
}

export function CameraSection({ enabled, onToggle }: CameraSectionProps) {
  const { models, loading, startDownload, removeModel } = useModels();

  const faceLandmarker = models.find((m) => m.id === "face_landmarker");

  return (
    <div className="bg-gray-800/50 rounded-xl p-5 space-y-4">
      <h2 className="text-sm font-semibold text-gray-300">カメラ設定</h2>

      {/* Camera toggle */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-300">カメラによる状態検知</p>
          <p className="text-xs text-gray-500 mt-0.5">
            カメラで姿勢・表情を検知し、状態判定に利用します
          </p>
        </div>
        <button
          onClick={() => onToggle(!enabled)}
          className={`relative w-11 h-6 rounded-full transition-colors ${
            enabled ? "bg-blue-600" : "bg-gray-700"
          }`}
        >
          <span
            className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
              enabled ? "translate-x-5" : ""
            }`}
          />
        </button>
      </div>

      {/* Face landmarker model card */}
      {loading ? (
        <div className="bg-gray-900/50 rounded-lg h-14 animate-pulse" />
      ) : (
        faceLandmarker && (
          <ModelCard
            model={faceLandmarker}
            onDownload={startDownload}
            onDelete={removeModel}
          />
        )
      )}
    </div>
  );
}
