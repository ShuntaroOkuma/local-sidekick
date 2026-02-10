import { app, BrowserWindow, ipcMain } from "electron";
import { join } from "path";
import { createTray, updateTrayIcon } from "./tray";
import { PythonBridge } from "./python-bridge";
import { showNotification } from "./notification";
import type { NotificationType } from "./notification";

let mainWindow: BrowserWindow | null = null;
let pythonBridge: PythonBridge | null = null;
let statePollingInterval: ReturnType<typeof setInterval> | null = null;

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    show: false,
    frame: true,
    titleBarStyle: "hiddenInset",
    backgroundColor: "#111827",
    webPreferences: {
      preload: join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  // In development, load from Vite dev server
  if (process.env.ELECTRON_RENDERER_URL) {
    win.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    win.loadFile(join(__dirname, "../dist/index.html"));
  }

  win.on("close", (event) => {
    event.preventDefault();
    win.hide();
  });

  return win;
}

function startStatePolling(): void {
  if (statePollingInterval) return;

  statePollingInterval = setInterval(async () => {
    if (!pythonBridge?.isRunning()) return;

    try {
      const port = pythonBridge.getPort();
      const res = await fetch(`http://localhost:${port}/api/state`);
      if (!res.ok) return;

      const state = await res.json();

      // Update tray icon based on state
      updateTrayIcon(state.state);

      // Check for notifications
      const notifRes = await fetch(
        `http://localhost:${port}/api/notifications/pending`
      );
      if (notifRes.ok) {
        const notifications = await notifRes.json();
        for (const notif of notifications) {
          showNotification(
            notif.type as NotificationType,
            (action: string) => {
              mainWindow?.webContents.send("notification-response", {
                type: notif.type,
                action,
              });
              // Report back to engine
              fetch(
                `http://localhost:${port}/api/notifications/${notif.id}/respond`,
                {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ action }),
                }
              ).catch(() => {});
            }
          );
        }
      }
    } catch {
      // Engine not ready yet
    }
  }, 5000);
}

function stopStatePolling(): void {
  if (statePollingInterval) {
    clearInterval(statePollingInterval);
    statePollingInterval = null;
  }
}

app.whenReady().then(async () => {
  mainWindow = createWindow();

  // Create tray
  createTray(mainWindow);

  // Setup IPC handlers
  ipcMain.handle("get-engine-url", () => {
    const port = pythonBridge?.getPort() ?? 18080;
    return `http://localhost:${port}`;
  });

  ipcMain.handle("get-app-version", () => {
    return app.getVersion();
  });

  ipcMain.handle("get-platform", () => {
    return process.platform;
  });

  ipcMain.on("notification-response", (_event, data) => {
    const { type, action } = data;
    console.log(`Notification response: ${type} -> ${action}`);
  });

  // Start Python Engine
  pythonBridge = new PythonBridge();
  try {
    await pythonBridge.spawn();
    console.log("Python Engine started successfully");
    startStatePolling();
  } catch (err) {
    console.error("Failed to start Python Engine:", err);
    // App still works without engine - shows disconnected state
  }
});

app.on("window-all-closed", () => {
  // On macOS, keep the app running in tray
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", async () => {
  stopStatePolling();
  mainWindow?.removeAllListeners("close");
  mainWindow?.close();

  if (pythonBridge) {
    await pythonBridge.stop();
  }
});

app.on("activate", () => {
  if (mainWindow) {
    mainWindow.show();
  }
});
