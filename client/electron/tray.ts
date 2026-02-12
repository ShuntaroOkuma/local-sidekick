import { Tray, Menu, nativeImage, BrowserWindow, app } from "electron";

let tray: Tray | null = null;
let mainWindow: BrowserWindow | null = null;

// RGBA colors for each state (drawn as a filled circle in the tray icon)
const STATE_COLORS: Record<string, [number, number, number, number]> = {
  focused: [0x34, 0xc7, 0x59, 255], // green
  drowsy: [0xed, 0x4a, 0x4a, 255], // red
  distracted: [0xf5, 0xc5, 0x42, 255], // yellow
  away: [0xbb, 0xbb, 0xbb, 255], // light gray
  idle: [0xbb, 0xbb, 0xbb, 255], // light gray
  disconnected: [0x99, 0x99, 0x99, 160], // gray, semi-transparent (hollow feel)
};

function createCircleIcon(
  rgba: [number, number, number, number],
): Electron.NativeImage {
  // 32x32 raw RGBA buffer (renders as 16x16 @2x Retina)
  const size = 32;
  const radius = 12;
  const center = size / 2;
  const buf = Buffer.alloc(size * size * 4, 0);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - center + 0.5;
      const dy = y - center + 0.5;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist <= radius) {
        // Anti-alias the edge
        const alpha = Math.min(1, radius - dist + 0.5);
        const offset = (y * size + x) * 4;
        buf[offset] = rgba[0];
        buf[offset + 1] = rgba[1];
        buf[offset + 2] = rgba[2];
        buf[offset + 3] = Math.round(rgba[3] * alpha);
      }
    }
  }

  return nativeImage.createFromBuffer(buf, {
    width: size,
    height: size,
    scaleFactor: 2.0,
  });
}

function getStateIcon(state: string): Electron.NativeImage {
  const color = STATE_COLORS[state] || STATE_COLORS.disconnected;
  return createCircleIcon(color);
}

export function createTray(window: BrowserWindow): Tray {
  mainWindow = window;

  tray = new Tray(getStateIcon("disconnected"));
  tray.setToolTip("Local Sidekick");

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

  tray.setImage(getStateIcon(state));
  tray.setToolTip(`Local Sidekick - ${state}`);
}
