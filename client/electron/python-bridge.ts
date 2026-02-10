import { ChildProcess, spawn } from "child_process";
import { join } from "path";
import { app } from "electron";

export class PythonBridge {
  private process: ChildProcess | null = null;
  private port: number = 18080;
  private pythonPath: string;
  private enginePath: string;

  constructor() {
    // Default Python venv path relative to app root
    const appRoot = app.isPackaged
      ? join(app.getAppPath(), "..")
      : join(__dirname, "../..");

    this.pythonPath =
      process.env.PYTHON_PATH || join(appRoot, "engine/.venv/bin/python");
    this.enginePath = process.env.ENGINE_PATH || join(appRoot, "engine");
  }

  async spawn(): Promise<void> {
    return new Promise((resolve, reject) => {
      console.log(`Starting Python Engine...`);
      console.log(`Python path: ${this.pythonPath}`);
      console.log(`Engine path: ${this.enginePath}`);

      try {
        this.process = spawn(this.pythonPath, ["-m", "engine.main"], {
          cwd: this.enginePath,
          env: {
            ...process.env,
            ENGINE_PORT: String(this.port),
          },
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
        console.log("Force killing Python Engine (SIGKILL)");
        proc.kill("SIGKILL");
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
