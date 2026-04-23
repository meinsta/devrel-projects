import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, unlinkSync } from "fs";
import { spawn } from "child_process";
import path from "path";
import yaml from "js-yaml";

interface ServiceConfig {
  command: string;
  port?: number;
  dir?: string;
}

interface InfraConfig {
  services: Record<string, ServiceConfig>;
}

export async function infraStart(configPath: string): Promise<void> {
  if (!configPath || !existsSync(configPath)) {
    console.error("no cage-infra.yaml found");
    console.error("\nexample cage-infra.yaml:\n");
    console.error("  services:");
    console.error("    backend:");
    console.error("      command: uv run uvicorn main:app --port $PORT");
    console.error("      port: 4100");
    console.error("      dir: backend/");
    process.exit(1);
  }

  const content = readFileSync(configPath, "utf-8");
  const config = yaml.load(content) as InfraConfig;

  if (!config?.services) {
    console.error("cage-infra.yaml has no services defined");
    process.exit(1);
  }

  const pidDir = ".cage/pids";
  mkdirSync(pidDir, { recursive: true });

  console.log("starting infrastructure...");

  for (const [name, svc] of Object.entries(config.services)) {
    const port = svc.port || 4000;
    const cmd = svc.command.replace(/\$PORT/g, String(port));
    const workdir = svc.dir || ".";

    const logPath = `.cage/${name}.log`;

    console.log(`  starting ${name} on port ${port}...`);

    const logFile = Bun.file(logPath);
    const writer = logFile.writer();

    const proc = spawn("sh", ["-c", cmd], {
      cwd: workdir,
      env: { ...process.env, PORT: String(port) },
      stdio: ["ignore", "pipe", "pipe"],
      detached: true,
    });

    proc.stdout?.on("data", (data) => writer.write(data));
    proc.stderr?.on("data", (data) => writer.write(data));
    proc.unref();

    if (proc.pid) {
      writeFileSync(path.join(pidDir, `${name}.pid`), String(proc.pid));
      console.log(`  ${name} started (pid=${proc.pid}, port=${port})`);
    } else {
      console.error(`  ${name} failed to start`);
    }
  }

  console.log(`\nall services started. logs in .cage/`);
}

export async function infraStop(pidDir: string): Promise<void> {
  if (!existsSync(pidDir)) {
    console.log("no running services found");
    return;
  }

  console.log("stopping infrastructure...");

  const pidFiles = readdirSync(pidDir).filter(f => f.endsWith(".pid"));
  for (const pidFile of pidFiles) {
    const name = pidFile.replace(".pid", "");
    const pidPath = path.join(pidDir, pidFile);
    const pid = parseInt(readFileSync(pidPath, "utf-8").trim(), 10);

    try {
      // try to kill the process group first
      process.kill(-pid, "SIGTERM");
      console.log(`  stopped ${name} (pid=${pid})`);
    } catch {
      try {
        process.kill(pid, "SIGTERM");
        console.log(`  stopped ${name} (pid=${pid})`);
      } catch {
        console.log(`  ${name} already stopped`);
      }
    }

    unlinkSync(pidPath);
  }

  console.log("all services stopped");
}

export async function infraStatus(pidDir: string): Promise<void> {
  if (!existsSync(pidDir)) {
    console.log("no services registered");
    return;
  }

  console.log("=== infrastructure status ===\n");

  const pidFiles = readdirSync(pidDir).filter(f => f.endsWith(".pid"));
  for (const pidFile of pidFiles) {
    const name = pidFile.replace(".pid", "");
    const pid = parseInt(readFileSync(path.join(pidDir, pidFile), "utf-8").trim(), 10);

    try {
      process.kill(pid, 0); // check if alive
      console.log(`  ${name}: running (pid=${pid})`);
    } catch {
      console.log(`  ${name}: stopped (stale pid=${pid})`);
    }
  }
}
