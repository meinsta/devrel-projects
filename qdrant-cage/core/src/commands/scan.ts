import { existsSync, readdirSync, readFileSync, writeFileSync, mkdirSync, statSync } from "fs";
import path from "path";

interface DetectedService {
  name: string;
  dir: string;
  framework: string;
  language: string;
  entryPoint?: string;
  testCommand?: string;
  envVars: string[];
}

const FRAMEWORK_DETECTORS: Array<{
  marker: string;
  detect: (dir: string) => { framework: string; language: string } | null;
}> = [
  {
    marker: "package.json",
    detect: (dir) => {
      try {
        const pkg = JSON.parse(readFileSync(path.join(dir, "package.json"), "utf-8"));
        const deps = { ...pkg.dependencies, ...pkg.devDependencies };
        if (deps["next"]) return { framework: "Next.js", language: "TypeScript/JavaScript" };
        if (deps["nuxt"]) return { framework: "Nuxt", language: "TypeScript/JavaScript" };
        if (deps["svelte"] || deps["@sveltejs/kit"]) return { framework: "SvelteKit", language: "TypeScript/JavaScript" };
        if (deps["express"]) return { framework: "Express", language: "TypeScript/JavaScript" };
        if (deps["fastify"]) return { framework: "Fastify", language: "TypeScript/JavaScript" };
        if (deps["hono"]) return { framework: "Hono", language: "TypeScript/JavaScript" };
        if (deps["react"]) return { framework: "React", language: "TypeScript/JavaScript" };
        if (deps["vue"]) return { framework: "Vue", language: "TypeScript/JavaScript" };
        return { framework: "Node.js", language: "TypeScript/JavaScript" };
      } catch {
        return { framework: "Node.js", language: "JavaScript" };
      }
    },
  },
  {
    marker: "pyproject.toml",
    detect: (dir) => {
      try {
        const content = readFileSync(path.join(dir, "pyproject.toml"), "utf-8");
        if (content.includes("fastapi")) return { framework: "FastAPI", language: "Python" };
        if (content.includes("flask")) return { framework: "Flask", language: "Python" };
        if (content.includes("django")) return { framework: "Django", language: "Python" };
        if (content.includes("litestar")) return { framework: "Litestar", language: "Python" };
        return { framework: "Python", language: "Python" };
      } catch {
        return { framework: "Python", language: "Python" };
      }
    },
  },
  {
    marker: "Cargo.toml",
    detect: () => ({ framework: "Rust", language: "Rust" }),
  },
  {
    marker: "go.mod",
    detect: () => ({ framework: "Go", language: "Go" }),
  },
  {
    marker: "mix.exs",
    detect: () => ({ framework: "Elixir", language: "Elixir" }),
  },
];

function detectTestCommand(dir: string): string | undefined {
  const pkgPath = path.join(dir, "package.json");
  if (existsSync(pkgPath)) {
    try {
      const pkg = JSON.parse(readFileSync(pkgPath, "utf-8"));
      if (pkg.scripts?.test) return `pnpm test`;
    } catch {}
  }

  const pyprojectPath = path.join(dir, "pyproject.toml");
  if (existsSync(pyprojectPath)) {
    const content = readFileSync(pyprojectPath, "utf-8");
    if (content.includes("[tool.pytest")) return "uv run pytest";
  }

  return undefined;
}

function detectEnvVars(dir: string): string[] {
  const envExample = path.join(dir, ".env.example");
  if (!existsSync(envExample)) return [];

  try {
    const content = readFileSync(envExample, "utf-8");
    return content
      .split("\n")
      .filter(line => line.includes("=") && !line.startsWith("#"))
      .map(line => line.split("=")[0].trim());
  } catch {
    return [];
  }
}

function shouldSkipDir(name: string): boolean {
  const skip = [
    "node_modules", ".git", ".cage", "__pycache__", ".next",
    "dist", "build", ".venv", "venv", "target", ".tox",
  ];
  return skip.includes(name) || name.startsWith(".");
}

function findServices(projectRoot: string, maxDepth: number = 3): DetectedService[] {
  const services: DetectedService[] = [];

  function walk(dir: string, depth: number) {
    if (depth > maxDepth) return;

    for (const detector of FRAMEWORK_DETECTORS) {
      const markerPath = path.join(dir, detector.marker);
      if (existsSync(markerPath)) {
        // don't detect the root if it's just a monorepo config
        if (dir === projectRoot && existsSync(path.join(dir, "pnpm-workspace.yaml"))) {
          continue; // skip root, scan children
        }

        const result = detector.detect(dir);
        if (result) {
          const relativePath = path.relative(projectRoot, dir) || ".";
          services.push({
            name: path.basename(dir),
            dir: relativePath,
            framework: result.framework,
            language: result.language,
            testCommand: detectTestCommand(dir),
            envVars: detectEnvVars(dir),
          });
          return; // don't recurse into detected services
        }
      }
    }

    // recurse into subdirectories
    try {
      const entries = readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isDirectory() && !shouldSkipDir(entry.name)) {
          walk(path.join(dir, entry.name), depth + 1);
        }
      }
    } catch {}
  }

  walk(projectRoot, 0);
  return services;
}

function generateAgentContext(service: DetectedService, projectName: string): string {
  const lines = [
    `# ${service.name}`,
    "",
    `## stack`,
    `- framework: ${service.framework}`,
    `- language: ${service.language}`,
    service.testCommand ? `- test: \`${service.testCommand}\`` : null,
    "",
    `## directory`,
    `- path: ${service.dir}`,
    "",
  ].filter(Boolean);

  if (service.envVars.length > 0) {
    lines.push("## environment variables");
    for (const v of service.envVars) {
      lines.push(`- \`${v}\``);
    }
    lines.push("");
  }

  lines.push(
    "## cage project",
    "",
    `this service is part of the ${projectName} project, managed by CAGE.`,
    "cross-service contracts live in shared/. never duplicate contract values.",
    "use cage commands for lifecycle management. see root CLAUDE.md for details.",
  );

  return lines.join("\n") + "\n";
}

export async function scan(projectRoot: string): Promise<void> {
  const absRoot = path.resolve(projectRoot);
  const projectName = path.basename(absRoot);

  console.log(`scanning ${absRoot}...\n`);

  // phase 1: marker-based detection
  const services = findServices(absRoot);

  if (services.length === 0) {
    console.log("no services detected. is this the project root?");
    console.log("looking for: package.json, pyproject.toml, Cargo.toml, go.mod");
    return;
  }

  console.log(`detected ${services.length} service(s):\n`);

  for (const svc of services) {
    console.log(`  ${svc.name} (${svc.framework}) -> ${svc.dir}`);
    if (svc.testCommand) console.log(`    test: ${svc.testCommand}`);
    if (svc.envVars.length > 0) console.log(`    env vars: ${svc.envVars.join(", ")}`);

    // generate per-service CLAUDE.md + AGENTS.md
    const serviceDir = path.join(absRoot, svc.dir);
    const content = generateAgentContext(svc, projectName);

    for (const filename of ["CLAUDE.md", "AGENTS.md"]) {
      const filePath = path.join(serviceDir, filename);
      if (!existsSync(filePath)) {
        writeFileSync(filePath, content);
        console.log(`    created ${filename}`);
      } else {
        console.log(`    ${filename} already exists, skipping`);
      }
    }
  }

  // phase 2: vector-based analysis (if index exists)
  const hasIndex = existsSync(path.join(absRoot, ".cage/vectors"));
  if (hasIndex) {
    console.log("\n  vector analysis:");
    try {
      const { openShard, closeShard, vectorSearch } = await import("../vector-engine");
      openShard(absRoot);

      // find API entry points
      const entryPoints = await vectorSearch("API route handler endpoint", 5, "function");
      if (entryPoints.length > 0) {
        console.log("    API entry points:");
        for (const ep of entryPoints.filter(e => e.score > 0.4)) {
          console.log(`      ${ep.filePath}:${ep.startLine} (${ep.score.toFixed(3)})`);
        }
      }

      // find test files
      const testCode = await vectorSearch("test suite describe it expect assert", 5, "file");
      if (testCode.length > 0) {
        console.log("    test files:");
        for (const t of testCode.filter(e => e.score > 0.4)) {
          console.log(`      ${t.filePath} (${t.score.toFixed(3)})`);
        }
      }

      closeShard();
    } catch (err: any) {
      console.log(`    vector analysis unavailable: ${err.message}`);
    }
  } else {
    console.log("\n  run 'cage index' for vector-powered analysis (entry points, test files, patterns)");
  }

  console.log(`\nscan complete. ${services.length} services detected.`);
}
