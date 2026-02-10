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

function createFallbackIcon(): Electron.NativeImage {
  // 16x16 PNG with a simple dark circle (template image for macOS)
  // Generated as a minimal valid PNG buffer
  const size = 16;
  const canvas = Buffer.alloc(size * size * 4, 0);
  const cx = size / 2;
  const cy = size / 2;
  const r = 6;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - cx + 0.5;
      const dy = y - cy + 0.5;
      if (dx * dx + dy * dy <= r * r) {
        const offset = (y * size + x) * 4;
        canvas[offset] = 0;     // R
        canvas[offset + 1] = 0; // G
        canvas[offset + 2] = 0; // B
        canvas[offset + 3] = 200; // A
      }
    }
  }
  return nativeImage.createFromBuffer(canvas, { width: size, height: size });
}

function createTrayIcon(): Electron.NativeImage {
  const iconPath = join(__dirname, "../public/icon.png");
  const icon = nativeImage.createFromPath(iconPath);
  if (!icon.isEmpty()) {
    return icon.resize({ width: 16, height: 16 });
  }
  return createFallbackIcon();
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
