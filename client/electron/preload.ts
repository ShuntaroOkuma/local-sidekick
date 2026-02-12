import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  getEngineUrl: (): Promise<string> => ipcRenderer.invoke("get-engine-url"),

  onNotification: (callback: (data: { type: string; message: string }) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, data: { type: string; message: string }) => callback(data);
    ipcRenderer.on("notification", handler);
    return () => ipcRenderer.removeListener("notification", handler);
  },

  sendNotificationResponse: (type: string, action: string): void => {
    ipcRenderer.send("notification-response", { type, action });
  },

  getAppVersion: (): Promise<string> => ipcRenderer.invoke("get-app-version"),

  getPlatform: (): Promise<string> => ipcRenderer.invoke("get-platform"),

  onNavigate: (callback: (path: string) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, path: string) => callback(path);
    ipcRenderer.on("navigate", handler);
    return () => ipcRenderer.removeListener("navigate", handler);
  },

  getAvatarEnabled: (): Promise<boolean> => ipcRenderer.invoke("get-avatar-enabled"),

  setAvatarEnabled: (enabled: boolean): Promise<void> => ipcRenderer.invoke("set-avatar-enabled", enabled),
});
