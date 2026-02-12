import { BrowserWindow, screen } from "electron";
import { join } from "path";

let avatarWindow: BrowserWindow | null = null;

export function createAvatarWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 200,
    height: 300,
    transparent: true,
    frame: false,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    show: false,
    webPreferences: {
      preload: join(__dirname, "preload-avatar.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.setAlwaysOnTop(true, "floating");
  win.setVisibleOnAllWorkspaces(true);
  win.setIgnoreMouseEvents(true, { forward: true });

  // Position at bottom-right of primary display
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;
  win.setPosition(width - 220, height - 320);

  avatarWindow = win;
  return win;
}

export function getAvatarWindow(): BrowserWindow | null {
  return avatarWindow;
}

export function showAvatarWindow(): void {
  avatarWindow?.show();
}

export function hideAvatarWindow(): void {
  avatarWindow?.hide();
}

export function sendToAvatar(channel: string, data: unknown): void {
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    avatarWindow.webContents.send(channel, data);
  }
}
