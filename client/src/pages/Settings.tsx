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
  const [cloudUrlInput, setCloudUrlInput] = useState(settings.cloud_run_url ?? "");
  const [cloudUrlSaving, setCloudUrlSaving] = useState(false);
  const [cloudUrlSaved, setCloudUrlSaved] = useState(false);

  useEffect(() => {
    setForm(settings);
    setCloudUrlInput(settings.cloud_run_url ?? "");
  }, [settings]);

  const handleCloudAuth = async (mode: "login" | "register") => {
    setCloudLoading(true);
    setCloudError(null);
    try {
      const fn = mode === "login" ? api.cloudLogin : api.cloudRegister;
      await fn(cloudEmail, cloudPassword);
      setCloudEmail("");
      setCloudPassword("");
      await refetch();
    } catch {
      setCloudError(mode === "login" ? "ログインに失敗しました" : "登録に失敗しました");
    } finally {
      setCloudLoading(false);
    }
  };

  const handleCloudUrlSave = async () => {
    setCloudUrlSaving(true);
    setCloudUrlSaved(false);
    setCloudError(null);
    try {
      await api.cloudCheckUrl(cloudUrlInput);
    } catch {
      setCloudError("Cloud Run URLに接続できません。URLを確認してください。");
      setCloudUrlSaving(false);
      return;
    }
    const success = await updateSettings({ ...form, cloud_run_url: cloudUrlInput });
    setCloudUrlSaving(false);
    if (success) {
      setCloudUrlSaved(true);
      setTimeout(() => setCloudUrlSaved(false), 3000);
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

            {/* Step 1: Cloud Run URL */}
            <div>
              <label className="text-xs text-gray-500 block mb-1">
                Cloud Run URL
              </label>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={cloudUrlInput}
                  onChange={(e) => setCloudUrlInput(e.target.value)}
                  placeholder="https://your-service.run.app"
                  className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
                />
                <button
                  onClick={handleCloudUrlSave}
                  disabled={cloudUrlSaving || !cloudUrlInput}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap"
                >
                  {cloudUrlSaving ? "接続中..." : "接続"}
                </button>
              </div>
              {cloudUrlSaved && (
                <p className="text-xs text-green-400 mt-1">接続しました</p>
              )}
            </div>

            {cloudError && (
              <p className="text-xs text-red-400">{cloudError}</p>
            )}

            {/* Step 2: Auth (only shown when URL is saved) */}
            {settings.cloud_run_url && (
              <>
                <div className="border-t border-gray-700 pt-4">
                  <h3 className="text-xs font-semibold text-gray-400 mb-3">
                    認証
                  </h3>
                </div>

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
                        onClick={() => handleCloudAuth("login")}
                        disabled={cloudLoading || !cloudEmail || !cloudPassword}
                        className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
                      >
                        {cloudLoading ? "処理中..." : "ログイン"}
                      </button>
                    </div>
                  </div>
                )}
              </>
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
