import { Tray, Menu, nativeImage, BrowserWindow, app } from "electron";
import { join } from "path";

let tray: Tray | null = null;
let mainWindow: BrowserWindow | null = null;

const STATE_ICONS: Record<string, string> = {
  focused: "🟢",
  drowsy: "🔴",
  distracted: "🟡",
  away: "⚪",
  idle: "⚪",
  disconnected: "⭕",
};

function createTrayIcon(): Electron.NativeImage {
  // Create a simple 16x16 template image for macOS menu bar
  // In production, this would be a proper .png template image
  const icon = nativeImage.createEmpty();
  try {
    const iconPath = join(__dirname, "../public/icon.png");
    return nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  } catch {
    // Fallback: create a simple colored icon
    return nativeImage.createEmpty();
  }
}

export function createTray(window: BrowserWindow): Tray {
  mainWindow = window;

  const icon = createTrayIcon();
  tray = new Tray(icon);
  tray.setToolTip("Local Sidekick");

  // Set title for macOS menu bar (shows text next to icon)
  tray.setTitle("LS");

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Dashboard",
      click: () => {
        mainWindow?.show();
        mainWindow?.focus();
      },
    },
    { type: "separator" },
    {
      label: "Settings",
      click: () => {
        mainWindow?.show();
        mainWindow?.focus();
        mainWindow?.webContents.send("navigate", "/settings");
      },
    },
    { type: "separator" },
    {
      label: "Quit Local Sidekick",
      click: () => {
        app.quit();
      },
    },
  ]);

  // Left click: toggle window
  tray.on("click", () => {
    if (mainWindow?.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow?.show();
      mainWindow?.focus();
    }
  });

  // Right click: context menu
  tray.on("right-click", () => {
    tray?.popUpContextMenu(contextMenu);
  });

  return tray;
}

export function updateTrayIcon(state: string): void {
  if (!tray) return;

  const stateLabel = STATE_ICONS[state] || STATE_ICONS.disconnected;
  tray.setTitle(stateLabel);
  tray.setToolTip(`Local Sidekick - ${state}`);
}
