import { ChildProcess, spawn } from "child_process";
import { copyFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { app } from "electron";

const IS_WINDOWS = process.platform === "win32";

export class PythonBridge {
  private process: ChildProcess | null = null;
  private port: number = 18080;
  private pythonPath: string;
  private enginePath: string;
  private modelsDir: string;

  constructor() {
    const resourcesPath = join(app.getAppPath(), "..");

    if (app.isPackaged) {
      // Packaged: standalone Python + engine bundled in Resources/
      this.pythonPath = IS_WINDOWS
        ? join(resourcesPath, "python", "python.exe")
        : join(resourcesPath, "python", "bin", "python3");
      this.enginePath = join(resourcesPath, "engine");
    } else {
      // Development: use venv
      const appRoot = join(__dirname, "../..");
      const defaultPython = IS_WINDOWS
        ? join(appRoot, "engine", ".venv", "Scripts", "python.exe")
        : join(appRoot, "engine", ".venv", "bin", "python");
      this.pythonPath = process.env.PYTHON_PATH || defaultPython;
      this.enginePath = process.env.ENGINE_PATH || join(appRoot, "engine");
    }

    // Writable models directory for downloads (packaged app Resources/ is read-only)
    this.modelsDir = join(app.getPath("home"), ".local-sidekick", "models");
  }

  /**
   * Copy bundled seed models (e.g. face_landmarker.task) to user's writable models dir.
   * Only runs in packaged mode; skips files that already exist.
   */
  private seedModels(): void {
    if (!app.isPackaged) return;

    mkdirSync(this.modelsDir, { recursive: true });

    const bundledFaceLandmarker = join(
      this.enginePath,
      "models",
      "face_landmarker.task"
    );
    const targetFaceLandmarker = join(this.modelsDir, "face_landmarker.task");

    if (
      existsSync(bundledFaceLandmarker) &&
      !existsSync(targetFaceLandmarker)
    ) {
      console.log("Seeding face_landmarker.task to user models directory");
      copyFileSync(bundledFaceLandmarker, targetFaceLandmarker);
    }
  }

  async spawn(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.seedModels();

      console.log(`Starting Python Engine...`);
      console.log(`Python path: ${this.pythonPath}`);
      console.log(`Engine path: ${this.enginePath}`);

      try {
        const env: Record<string, string> = {
          ...process.env,
          ENGINE_PORT: String(this.port),
        } as Record<string, string>;

        if (app.isPackaged) {
          // Point models to writable user directory
          env.SIDEKICK_MODELS_DIR = this.modelsDir;
          // Prevent user's Python env from interfering with standalone Python
          delete env.PYTHONHOME;
          delete env.PYTHONPATH;
        }

        this.process = spawn(this.pythonPath, ["-m", "engine.main"], {
          cwd: this.enginePath,
          env,
          stdio: ["pipe", "pipe", "pipe"],
        });

        this.process.stdout?.on("data", (data: Buffer) => {
          console.log(`[Engine] ${data.toString().trim()}`);
        });

        this.process.stderr?.on("data", (data: Buffer) => {
          console.error(`[Engine] ${data.toString().trim()}`);
        });

        this.process.on("error", (err: Error) => {
          console.error("Failed to start Python Engine:", err.message);
          this.process = null;
        });

        this.process.on("exit", (code: number | null) => {
          console.log(`Python Engine exited with code ${code}`);
          this.process = null;
        });

        // Wait for health check
        this.waitForHealth()
          .then(() => resolve())
          .catch((err) => {
            this.stop();
            reject(err);
          });
      } catch (err) {
        reject(err);
      }
    });
  }

  private async waitForHealth(): Promise<void> {
    const timeout = 30000; // 30 seconds
    const interval = 1000; // 1 second
    const start = Date.now();

    while (Date.now() - start < timeout) {
      try {
        const res = await fetch(`http://localhost:${this.port}/api/health`);
        if (res.ok) {
          console.log("Python Engine is ready");
          return;
        }
      } catch {
        // Not ready yet
      }
      await new Promise((r) => setTimeout(r, interval));
    }

    throw new Error("Python Engine health check timed out after 30 seconds");
  }

  async stop(): Promise<void> {
    if (!this.process) return;

    return new Promise((resolve) => {
      const proc = this.process;
      if (!proc) {
        resolve();
        return;
      }

      // Set up force-kill timeout
      const killTimeout = setTimeout(() => {
        console.log("Force killing Python Engine");
        if (IS_WINDOWS) {
          // SIGKILL is not supported on Windows; use taskkill
          spawn("taskkill", ["/pid", String(proc.pid), "/f", "/t"]);
        } else {
          proc.kill("SIGKILL");
        }
        this.process = null;
        resolve();
      }, 5000);

      proc.on("exit", () => {
        clearTimeout(killTimeout);
        this.process = null;
        resolve();
      });

      // Try graceful shutdown first
      console.log("Stopping Python Engine (SIGTERM)");
      proc.kill("SIGTERM");
    });
  }

  isRunning(): boolean {
    return this.process !== null && !this.process.killed;
  }

  getPort(): number {
    return this.port;
  }
}
