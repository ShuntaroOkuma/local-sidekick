import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("avatarAPI", {
  getEngineUrl: (): Promise<string> => ipcRenderer.invoke("get-engine-url"),

  onStateUpdate: (callback: (data: unknown) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, data: unknown) =>
      callback(data);
    ipcRenderer.on("avatar-state-update", handler);
    return () => ipcRenderer.removeListener("avatar-state-update", handler);
  },

  onNotification: (callback: (data: unknown) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, data: unknown) =>
      callback(data);
    ipcRenderer.on("avatar-notification", handler);
    return () => ipcRenderer.removeListener("avatar-notification", handler);
  },
});
