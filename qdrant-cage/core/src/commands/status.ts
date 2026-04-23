import { existsSync, readFileSync, readdirSync } from "fs";
import { execSync } from "child_process";
import path from "path";

export async function status(): Promise<void> {
  console.log("=== CAGE status ===\n");

  // audits
  console.log("## audits");
  try {
    const tags = execSync("git tag -l 'audit/*' --sort=-creatordate", { encoding: "utf-8" }).trim();
    if (tags) {
      const seen = new Set<string>();
      for (const tag of tags.split("\n")) {
        const parts = tag.split("/");
        const surface = parts[1];
        if (seen.has(surface)) continue;
        seen.add(surface);
        const date = parts[2] || "unknown";
        console.log(`  ${surface}: last audited ${date}`);
      }
    } else {
      console.log("  no audits recorded. run /cage-audit to start.");
    }
  } catch {
    console.log("  no audits recorded");
  }

  console.log();

  // pipeline
  console.log("## feature pipeline");
  const pipelinePath = ".cage/pipeline.json";
  if (existsSync(pipelinePath)) {
    try {
      const data = JSON.parse(readFileSync(pipelinePath, "utf-8"));
      const features = Object.entries(data.features || {});
      if (features.length === 0) {
        console.log("  no features in pipeline");
      } else {
        for (const [name, feature] of features) {
          const f = feature as any;
          console.log(`  ${name}: ${f.state}`);
        }
      }
    } catch {
      console.log("  pipeline.json corrupt");
    }
  } else {
    console.log("  no pipeline initialized");
  }

  console.log();

  // worktrees
  console.log("## worktrees");
  try {
    const output = execSync("git worktree list", { encoding: "utf-8" }).trim();
    const lines = output.split("\n");
    if (lines.length <= 1) {
      console.log("  no active worktrees");
    } else {
      for (const line of lines.slice(1)) {
        console.log(`  ${line}`);
      }
    }
  } catch {
    console.log("  not a git repo");
  }

  console.log();

  // contracts
  console.log("## contracts");
  if (existsSync("shared")) {
    const files = readdirSync("shared").filter(f => f.endsWith(".json"));
    for (const f of files) {
      try {
        const data = JSON.parse(readFileSync(path.join("shared", f), "utf-8"));
        const keys = Object.keys(data).filter(k => !k.startsWith("_"));
        const totalEntries = keys.reduce((sum, k) => {
          const val = data[k];
          return sum + (typeof val === "object" ? Object.keys(val).length : 1);
        }, 0);
        console.log(`  ${f}: ${totalEntries} entries`);
      } catch {
        console.log(`  ${f}: invalid JSON`);
      }
    }
  } else {
    console.log("  no shared/ directory");
  }

  console.log();

  // index
  console.log("## vector index");
  const indexMeta = ".cage/index-meta.json";
  if (existsSync(indexMeta)) {
    try {
      const meta = JSON.parse(readFileSync(indexMeta, "utf-8"));
      console.log(`  last indexed: ${meta.lastIndexed}`);
      console.log(`  files: ${meta.totalFiles}, chunks: ${meta.totalChunks}`);
      if (meta.commit) console.log(`  commit: ${meta.commit}`);
    } catch {
      console.log("  index metadata corrupt");
    }
  } else {
    console.log("  not indexed. run 'cage index' to enable semantic search.");
  }

  console.log();

  // policy
  console.log("## policy");
  if (existsSync("cage.rules")) {
    const content = readFileSync("cage.rules", "utf-8");
    const lines = content.split("\n").filter(l => l.trim() && !l.trim().startsWith("#"));
    const blocked = lines.filter(l => l.startsWith("block")).length;
    const prompted = lines.filter(l => l.startsWith("prompt")).length;
    console.log(`  ${blocked} blocked, ${prompted} prompted`);
  } else {
    console.log("  no cage.rules found");
  }
}
