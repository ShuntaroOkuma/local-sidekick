import { app, BrowserWindow, ipcMain, powerMonitor, screen } from "electron";
import { join } from "path";
import { readFileSync } from "fs";
import { execFile } from "child_process";
import { createTray, updateTrayIcon } from "./tray";
import { PythonBridge } from "./python-bridge";
import {
  showNotification,
  setAvatarEnabled,
  isAvatarEnabled,
} from "./notification";
import type { NotificationType } from "./notification";
import {
  createAvatarWindow,
  sendToAvatar,
  showAvatarWindow,
  hideAvatarWindow,
} from "./avatar-window";

/** Read avatar_enabled from ~/.local-sidekick/config.json (before engine starts). */
function readAvatarEnabledFromConfig(): boolean {
  try {
    const configPath = join(
      app.getPath("home"),
      ".local-sidekick",
      "config.json",
    );
    const data = JSON.parse(readFileSync(configPath, "utf-8"));
    return data.avatar_enabled !== false; // default true
  } catch (err) {
    console.warn("Failed to read avatar config, using default:", err);
    return true;
  }
}

let mainWindow: BrowserWindow | null = null;
let avatarWin: BrowserWindow | null = null;
let pythonBridge: PythonBridge | null = null;
let statePollingTimeout: ReturnType<typeof setTimeout> | null = null;

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

  // Auto-reload if the renderer process dies (e.g. GPU reset after sleep)
  win.webContents.on("render-process-gone", (_event, details) => {
    console.log(`Renderer gone (reason: ${details.reason}) – reloading`);
    if (details.reason !== "clean-exit") {
      win.webContents.reload();
    }
  });

  return win;
}

function startStatePolling(): void {
  if (statePollingTimeout) return;

  const port = pythonBridge?.getPort() ?? 18080;

  async function poll(): Promise<void> {
    try {
      const res = await fetch(`http://localhost:${port}/api/state`);
      if (res.ok) {
        const state = await res.json();

        // Update tray icon based on state
        updateTrayIcon(state.state);

        // Forward state to avatar window
        sendToAvatar("avatar-state-update", state);

        // Check for notifications
        const notifRes = await fetch(
          `http://localhost:${port}/api/notifications/pending`,
        );
        if (notifRes.ok) {
          const notifications = await notifRes.json();
          for (const notif of notifications) {
            // Forward notification to avatar window
            sendToAvatar("avatar-notification", notif);

            // Play Glass notification sound
            execFile("afplay", ["/System/Library/Sounds/Purr.aiff"]);

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
                  },
                ).catch(() => {});
              },
            );
          }
        }
      }
    } catch {
      // Engine not ready yet
    }
    // Schedule next poll only after current one completes
    statePollingTimeout = setTimeout(poll, 5000);
  }

  // Start first poll
  statePollingTimeout = setTimeout(poll, 5000);
}

function stopStatePolling(): void {
  if (statePollingTimeout) {
    clearTimeout(statePollingTimeout);
    statePollingTimeout = null;
  }
}

app.whenReady().then(async () => {
  mainWindow = createWindow();

  // Create avatar overlay window (respect persisted setting)
  const savedAvatarEnabled = readAvatarEnabledFromConfig();
  avatarWin = createAvatarWindow();
  if (process.env.ELECTRON_RENDERER_URL) {
    // In dev, replace index.html with avatar.html in the dev server URL
    const devUrl = process.env.ELECTRON_RENDERER_URL.replace(/\/$/, "");
    avatarWin.loadURL(`${devUrl}/src/avatar/avatar.html`);
  } else {
    avatarWin.loadFile(join(__dirname, "../dist/src/avatar/avatar.html"));
  }
  avatarWin.once("ready-to-show", () => {
    setAvatarEnabled(savedAvatarEnabled);
    if (savedAvatarEnabled) {
      avatarWin?.show();
    }
  });

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

  ipcMain.handle("get-avatar-enabled", () => {
    return isAvatarEnabled();
  });

  ipcMain.handle("set-avatar-enabled", async (_event, enabled: boolean) => {
    setAvatarEnabled(enabled);
    if (enabled) {
      showAvatarWindow();
    } else {
      hideAvatarWindow();
    }
    // Persist to engine config
    const port = pythonBridge?.getPort() ?? 18080;
    try {
      await fetch(`http://localhost:${port}/api/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ avatar_enabled: enabled }),
      });
    } catch (err) {
      // Engine may not be running yet; the save button in Settings will also persist
      console.warn("Failed to persist avatar setting to engine:", err);
    }
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
  } catch (err) {
    console.error("Failed to start Python Engine:", err);
    console.log("Will poll for an externally started Engine on port 18080");
  }

  // Always start polling (works with both spawned and external Engine)
  startStatePolling();

  // Pause/resume monitoring on system sleep/wake and screen lock/unlock
  const enginePort = () => pythonBridge?.getPort() ?? 18080;

  async function pauseEngine(reason: string): Promise<void> {
    console.log(`${reason} – pausing engine monitoring`);
    stopStatePolling();
    try {
      const res = await fetch(
        `http://localhost:${enginePort()}/api/engine/pause`,
        {
          method: "POST",
        },
      );
      if (!res.ok) {
        console.warn(`Failed to pause engine: ${res.statusText}`);
      }
    } catch {
      console.log("Could not reach engine for pause (may not be running).");
    }
  }

  async function resumeEngine(reason: string): Promise<void> {
    console.log(`${reason} – resuming engine monitoring`);
    try {
      const res = await fetch(
        `http://localhost:${enginePort()}/api/engine/resume`,
        {
          method: "POST",
        },
      );
      if (!res.ok) {
        console.warn(`Failed to resume engine: ${res.statusText}`);
      }
    } catch {
      console.log("Could not reach engine for resume (may not be running).");
    }

    // Always restart polling and recover renderer regardless of engine
    // response — polling retries on its own, and reload fixes GPU context
    // loss which is independent of the engine state.
    startStatePolling();

    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.reload();
    }
  }

  powerMonitor.on("suspend", () => pauseEngine("System suspending"));
  powerMonitor.on("resume", () => resumeEngine("System resumed"));
  powerMonitor.on("lock-screen", () => pauseEngine("Screen locked"));
  powerMonitor.on("unlock-screen", () => resumeEngine("Screen unlocked"));

  // --- Display topology change handling (clamshell mode) ---
  // macOS does NOT fire "suspend" when entering clamshell mode with external
  // display + power + keyboard connected, so we listen for display events.
  let displayChangeTimer: ReturnType<typeof setTimeout> | null = null;

  function scheduleDisplayChangeHandler(): void {
    if (displayChangeTimer) clearTimeout(displayChangeTimer);
    displayChangeTimer = setTimeout(onDisplayChanged, 1000);
  }

  screen.on("display-added", scheduleDisplayChangeHandler);
  screen.on("display-removed", scheduleDisplayChangeHandler);
  screen.on("display-metrics-changed", (_event, _display, changedMetrics) => {
    if (
      changedMetrics.includes("workArea") ||
      changedMetrics.includes("bounds")
    ) {
      scheduleDisplayChangeHandler();
    }
  });

  async function onDisplayChanged(): Promise<void> {
    console.log(
      "Display topology changed – repositioning avatar & re-initializing camera",
    );

    // 1. Reposition avatar to bottom-right of new primary display
    if (avatarWin && !avatarWin.isDestroyed()) {
      const primary = screen.getPrimaryDisplay();
      const { width, height } = primary.workAreaSize;
      avatarWin.setPosition(width - 220, height - 320);
    }

    // 2. Trigger camera re-init via engine pause → resume.
    //    Call the API directly instead of pauseEngine/resumeEngine to avoid
    //    stopping state polling and reloading the main window.
    const port = enginePort();
    try {
      await fetch(`http://localhost:${port}/api/engine/pause`, {
        method: "POST",
      });
    } catch {
      // engine may not be running
    }

    await new Promise((resolve) => setTimeout(resolve, 500));

    try {
      await fetch(`http://localhost:${port}/api/engine/resume`, {
        method: "POST",
      });
    } catch {
      // engine may not be running
    }
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
