import { useState, useEffect } from "react";
import { useSettings } from "../hooks/useSettings";
import { ModelSection } from "../components/ModelSection";

export function Settings() {
  const { settings, loading, error, updateSettings } = useSettings();
  const [form, setForm] = useState(settings);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    setForm(settings);
  }, [settings]);

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);
    const success = await updateSettings(form);
    setSaving(false);
    if (success) {
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-gray-100">Settings</h1>
        <div className="bg-gray-800 rounded-lg p-8 animate-pulse h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-100">Settings</h1>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      <div className="space-y-5">
        {/* Working hours */}
        <div className="bg-gray-800/50 rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-300">稼働時間</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-500 block mb-1">
                開始時刻
              </label>
              <input
                type="time"
                value={form.working_hours_start}
                onChange={(e) =>
                  setForm({ ...form, working_hours_start: e.target.value })
                }
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">
                終了時刻
              </label>
              <input
                type="time"
                value={form.working_hours_end}
                onChange={(e) =>
                  setForm({ ...form, working_hours_end: e.target.value })
                }
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Notification limit */}
        <div className="bg-gray-800/50 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">
            通知上限（回/日）
          </h2>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="0"
              max="20"
              value={form.max_notifications_per_day}
              onChange={(e) =>
                setForm({
                  ...form,
                  max_notifications_per_day: parseInt(e.target.value),
                })
              }
              className="flex-1 accent-blue-500"
            />
            <span className="text-sm text-gray-300 w-8 text-center font-mono">
              {form.max_notifications_per_day}
            </span>
          </div>
        </div>

        {/* Toggles */}
        <div className="bg-gray-800/50 rounded-xl p-5 space-y-4">
          {/* Camera toggle */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-300">カメラ</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                カメラによる状態検知を有効にする
              </p>
            </div>
            <button
              onClick={() =>
                setForm({ ...form, camera_enabled: !form.camera_enabled })
              }
              className={`relative w-11 h-6 rounded-full transition-colors ${
                form.camera_enabled ? "bg-blue-600" : "bg-gray-700"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  form.camera_enabled ? "translate-x-5" : ""
                }`}
              />
            </button>
          </div>

          {/* Sync toggle */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-300">
                サーバ同期
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Cloud Run APIとの設定・統計同期
              </p>
            </div>
            <button
              onClick={() =>
                setForm({ ...form, sync_enabled: !form.sync_enabled })
              }
              className={`relative w-11 h-6 rounded-full transition-colors ${
                form.sync_enabled ? "bg-blue-600" : "bg-gray-700"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  form.sync_enabled ? "translate-x-5" : ""
                }`}
              />
            </button>
          </div>
        </div>

        {/* AI Model settings */}
        <ModelSection
          currentTier={form.model_tier ?? "lightweight"}
          onTierChange={(tier) => setForm({ ...form, model_tier: tier })}
        />
      </div>

      {/* Save button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {saving ? "保存中..." : "保存"}
        </button>
        {saveSuccess && (
          <span className="text-sm text-green-400">保存しました</span>
        )}
      </div>
    </div>
  );
}
