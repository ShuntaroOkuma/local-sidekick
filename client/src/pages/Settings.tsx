import { useState, useEffect } from "react";
import { useSettings } from "../hooks/useSettings";
import { CameraSection } from "../components/CameraSection";
import { ModelSection } from "../components/ModelSection";
import { api } from "../lib/api";

export function Settings() {
  const { settings, loading, error, updateSettings, refetch } = useSettings();
  const [form, setForm] = useState(settings);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [cloudEmail, setCloudEmail] = useState("");
  const [cloudPassword, setCloudPassword] = useState("");
  const [cloudLoading, setCloudLoading] = useState(false);
  const [cloudError, setCloudError] = useState<string | null>(null);

  useEffect(() => {
    setForm(settings);
  }, [settings]);

  const handleCloudLogin = async () => {
    setCloudLoading(true);
    setCloudError(null);
    try {
      await api.cloudLogin(cloudEmail, cloudPassword);
      setCloudEmail("");
      setCloudPassword("");
      await refetch();
    } catch {
      setCloudError("ログインに失敗しました");
    } finally {
      setCloudLoading(false);
    }
  };

  const handleCloudRegister = async () => {
    setCloudLoading(true);
    setCloudError(null);
    try {
      await api.cloudRegister(cloudEmail, cloudPassword);
      setCloudEmail("");
      setCloudPassword("");
      await refetch();
    } catch {
      setCloudError("登録に失敗しました");
    } finally {
      setCloudLoading(false);
    }
  };

  const handleCloudLogout = async () => {
    setCloudLoading(true);
    setCloudError(null);
    try {
      await api.cloudLogout();
      await refetch();
    } catch {
      setCloudError("ログアウトに失敗しました");
    } finally {
      setCloudLoading(false);
    }
  };

  const handleAvatarToggle = async () => {
    const next = !form.avatar_enabled;
    setForm({ ...form, avatar_enabled: next });
    // Immediately show/hide the avatar window via IPC
    await window.electronAPI?.setAvatarEnabled(next);
  };

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

        {/* Avatar toggle */}
        <div className="bg-gray-800/50 rounded-xl p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-300">アバター</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                デスクトップにアバターを表示する
              </p>
            </div>
            <button
              onClick={handleAvatarToggle}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                form.avatar_enabled ? "bg-blue-600" : "bg-gray-700"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  form.avatar_enabled ? "translate-x-5" : ""
                }`}
              />
            </button>
          </div>
        </div>

        {/* Camera settings */}
        <CameraSection
          enabled={form.camera_enabled}
          onToggle={(enabled) => setForm({ ...form, camera_enabled: enabled })}
        />

        {/* Sync toggle */}
        <div className="bg-gray-800/50 rounded-xl p-5">
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

        {/* Cloud Run settings */}
        {form.sync_enabled && (
          <div className="bg-gray-800/50 rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold text-gray-300">
              Cloud Run 接続
            </h2>

            {/* Cloud Run URL */}
            <div>
              <label className="text-xs text-gray-500 block mb-1">
                Cloud Run URL
              </label>
              <input
                type="url"
                value={form.cloud_run_url ?? ""}
                onChange={(e) =>
                  setForm({ ...form, cloud_run_url: e.target.value })
                }
                placeholder="https://your-service.run.app"
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
              />
            </div>

            {cloudError && (
              <p className="text-xs text-red-400">{cloudError}</p>
            )}

            {settings.cloud_auth_email ? (
              /* Logged in state */
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-300">
                  {settings.cloud_auth_email} としてログイン中
                </p>
                <button
                  onClick={handleCloudLogout}
                  disabled={cloudLoading}
                  className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 text-sm text-gray-300 rounded-lg transition-colors"
                >
                  {cloudLoading ? "処理中..." : "ログアウト"}
                </button>
              </div>
            ) : (
              /* Not logged in state */
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-gray-500 block mb-1">
                    メールアドレス
                  </label>
                  <input
                    type="email"
                    value={cloudEmail}
                    onChange={(e) => setCloudEmail(e.target.value)}
                    placeholder="user@example.com"
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">
                    パスワード
                  </label>
                  <input
                    type="password"
                    value={cloudPassword}
                    onChange={(e) => setCloudPassword(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleCloudLogin}
                    disabled={cloudLoading || !cloudEmail || !cloudPassword}
                    className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    {cloudLoading ? "処理中..." : "ログイン"}
                  </button>
                  <button
                    onClick={handleCloudRegister}
                    disabled={cloudLoading || !cloudEmail || !cloudPassword}
                    className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 text-sm text-gray-300 rounded-lg transition-colors"
                  >
                    {cloudLoading ? "処理中..." : "新規登録"}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

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
