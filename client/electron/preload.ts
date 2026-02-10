import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  getEngineUrl: (): Promise<string> => ipcRenderer.invoke("get-engine-url"),

  onNotification: (callback: (data: { type: string; message: string }) => void): void => {
    ipcRenderer.on("notification", (_event, data) => callback(data));
  },

  sendNotificationResponse: (type: string, action: string): void => {
    ipcRenderer.send("notification-response", { type, action });
  },

  getAppVersion: (): Promise<string> => ipcRenderer.invoke("get-app-version"),

  getPlatform: (): Promise<string> => ipcRenderer.invoke("get-platform"),

  onNavigate: (callback: (path: string) => void): void => {
    ipcRenderer.on("navigate", (_event, path) => callback(path));
  },
});
