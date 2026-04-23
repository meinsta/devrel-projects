import { existsSync, readFileSync, readdirSync } from "fs";
import { execSync } from "child_process";
import path from "path";

interface DiagnosticResult {
  name: string;
  status: "ok" | "warn" | "fail";
  message: string;
  fix?: string;
}

export async function doctor(projectRoot: string): Promise<void> {
  console.log("=== cage doctor ===\n");

  const results: DiagnosticResult[] = [];

  // 1. check cage.rules exists
  const rulesPath = path.join(projectRoot, "cage.rules");
  if (existsSync(rulesPath)) {
    results.push({ name: "cage.rules", status: "ok", message: "execution policy found" });
  } else {
    results.push({
      name: "cage.rules",
      status: "fail",
      message: "no execution policy",
      fix: "run 'cage init' to create cage.rules",
    });
  }

  // 2. check shared/ directory
  const sharedDir = path.join(projectRoot, "shared");
  if (existsSync(sharedDir)) {
    const jsonFiles = readdirSync(sharedDir).filter(f => f.endsWith(".json"));
    if (jsonFiles.length > 0) {
      results.push({ name: "shared/", status: "ok", message: `${jsonFiles.length} contract files` });
    } else {
      results.push({
        name: "shared/",
        status: "warn",
        message: "directory exists but no contract files",
        fix: "add contract JSON files to shared/",
      });
    }
  } else {
    results.push({
      name: "shared/",
      status: "fail",
      message: "no contracts directory",
      fix: "run 'cage init' to create shared/",
    });
  }

  // 3. check pre-commit hooks installed
  const preCommitConfig = path.join(projectRoot, ".pre-commit-config.yaml");
  if (existsSync(preCommitConfig)) {
    const hookDir = path.join(projectRoot, ".git/hooks/pre-commit");
    if (existsSync(hookDir)) {
      results.push({ name: "pre-commit", status: "ok", message: "hooks installed" });
    } else {
      results.push({
        name: "pre-commit",
        status: "warn",
        message: "config exists but hooks not installed",
        fix: "run 'pre-commit install'",
      });
    }
  } else {
    results.push({
      name: "pre-commit",
      status: "fail",
      message: "no .pre-commit-config.yaml",
      fix: "run 'cage init' to create pre-commit config",
    });
  }

  // 4. check CLAUDE.md exists
  const claudeMd = path.join(projectRoot, "CLAUDE.md");
  if (existsSync(claudeMd)) {
    results.push({ name: "CLAUDE.md", status: "ok", message: "agent context file found" });
  } else {
    results.push({
      name: "CLAUDE.md",
      status: "fail",
      message: "no agent context file",
      fix: "run 'cage init' to create CLAUDE.md",
    });
  }

  // 5. check docs structure
  const docsDir = path.join(projectRoot, "docs");
  if (existsSync(docsDir)) {
    const hasFeatures = existsSync(path.join(docsDir, "features"));
    const hasDesigns = existsSync(path.join(docsDir, "designs"));
    const hasBugs = existsSync(path.join(docsDir, "bugs.md"));
    const missing = [];
    if (!hasFeatures) missing.push("features/");
    if (!hasDesigns) missing.push("designs/");
    if (!hasBugs) missing.push("bugs.md");

    if (missing.length === 0) {
      results.push({ name: "docs/", status: "ok", message: "complete structure" });
    } else {
      results.push({
        name: "docs/",
        status: "warn",
        message: `missing: ${missing.join(", ")}`,
        fix: "run 'cage init' to create full docs structure",
      });
    }
  } else {
    results.push({
      name: "docs/",
      status: "fail",
      message: "no docs directory",
      fix: "run 'cage init' to create docs/",
    });
  }

  // 6. check vector index freshness
  const indexMeta = path.join(projectRoot, ".cage/index-meta.json");
  if (existsSync(indexMeta)) {
    try {
      const meta = JSON.parse(readFileSync(indexMeta, "utf-8"));
      const lastIndexed = meta.lastIndexed;
      const age = Date.now() - new Date(lastIndexed).getTime();
      const hours = Math.floor(age / 3600000);

      if (hours < 24) {
        results.push({ name: "vector index", status: "ok", message: `indexed ${hours}h ago` });
      } else {
        results.push({
          name: "vector index",
          status: "warn",
          message: `index is ${hours}h old`,
          fix: "run 'cage index' to re-index",
        });
      }
    } catch {
      results.push({
        name: "vector index",
        status: "warn",
        message: "index metadata corrupt",
        fix: "run 'cage index --force' to rebuild",
      });
    }
  } else {
    results.push({
      name: "vector index",
      status: "warn",
      message: "no vector index (semantic search disabled)",
      fix: "run 'cage index' to enable semantic code intelligence",
    });
  }

  // 7. check stale worktrees
  try {
    const worktreeOutput = execSync("git worktree list --porcelain", { encoding: "utf-8", cwd: projectRoot });
    const worktrees = worktreeOutput.split("\n\n").filter(Boolean);
    const staleCount = worktrees.length - 1; // exclude main

    if (staleCount === 0) {
      results.push({ name: "worktrees", status: "ok", message: "no active worktrees" });
    } else {
      results.push({ name: "worktrees", status: "ok", message: `${staleCount} active worktrees` });
    }
  } catch {
    results.push({ name: "worktrees", status: "ok", message: "not a git repo or no worktrees" });
  }

  // 8. check Serena MCP availability
  const cageConfig = path.join(projectRoot, "cage-config.yaml");
  if (existsSync(cageConfig)) {
    try {
      const config = readFileSync(cageConfig, "utf-8");
      if (config.includes("serena")) {
        results.push({ name: "serena", status: "ok", message: "LSP layer configured (hybrid mode)" });
      } else {
        results.push({
          name: "serena",
          status: "warn",
          message: "not configured (vector-only mode)",
          fix: "add serena config to cage-config.yaml for hybrid code intelligence",
        });
      }
    } catch {
      results.push({ name: "serena", status: "warn", message: "config parse error" });
    }
  } else {
    results.push({
      name: "serena",
      status: "warn",
      message: "no cage-config.yaml (vector-only mode)",
      fix: "create cage-config.yaml with serena config for hybrid code intelligence",
    });
  }

  // print results
  const fails = results.filter(r => r.status === "fail");
  const warns = results.filter(r => r.status === "warn");
  const oks = results.filter(r => r.status === "ok");

  for (const r of results) {
    const icon = r.status === "ok" ? "ok" : r.status === "warn" ? "WARN" : "FAIL";
    console.log(`  [${icon}] ${r.name}: ${r.message}`);
    if (r.fix) console.log(`         fix: ${r.fix}`);
  }

  console.log(`\n${oks.length} ok, ${warns.length} warnings, ${fails.length} failures`);

  if (fails.length > 0) {
    process.exit(1);
  }
}
