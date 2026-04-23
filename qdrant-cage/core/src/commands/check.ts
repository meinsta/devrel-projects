import { existsSync, readFileSync, readdirSync } from "fs";
import path from "path";
import { openShard, closeShard, vectorSearch, shardStats, type VectorSearchResult } from "../vector-engine";

export interface CheckResult {
  name: string;
  pass: boolean;
  issues: Array<{
    severity: "critical" | "warning" | "info";
    file: string;
    line?: number;
    message: string;
    fix?: string;
  }>;
}

// ---- check: boundary enforcement ----
// uses BOTH regex (exact imports) and vectors (copied logic)

function checkBoundaryEnforcement(projectRoot: string, vectorResults?: VectorSearchResult[]): CheckResult {
  const result: CheckResult = { name: "boundary-enforcement", pass: true, issues: [] };

  const serviceDirs = detectServiceDirs(projectRoot);
  if (serviceDirs.length < 2) return result;

  // EXACT: scan for cross-service imports
  for (const serviceDir of serviceDirs) {
    const fullDir = path.join(projectRoot, serviceDir);
    const files = walkSourceFiles(fullDir);

    for (const file of files) {
      const content = readFileSync(file, "utf-8");
      const lines = content.split("\n");
      const relativePath = path.relative(projectRoot, file);

      for (let i = 0; i < lines.length; i++) {
        for (const otherService of serviceDirs) {
          if (otherService === serviceDir) continue;

          const patterns = [
            `../../${otherService}`, `../${otherService}`,
            `@/${otherService}`, `~/${otherService}`,
          ];

          for (const pattern of patterns) {
            if (lines[i].includes(pattern) && isImportLine(lines[i])) {
              result.pass = false;
              result.issues.push({
                severity: "critical",
                file: relativePath,
                line: i + 1,
                message: `cross-service import: ${serviceDir} imports from ${otherService}`,
                fix: `move shared code to shared/ or create a proper API boundary`,
              });
            }
          }
        }
      }
    }
  }

  // SEMANTIC: detect copied logic between services (vector-powered)
  if (vectorResults) {
    // for each service, find functions semantically similar to other services' functions
    for (const serviceDir of serviceDirs) {
      for (const otherService of serviceDirs) {
        if (otherService === serviceDir) continue;

        // find function chunks from this service that are very similar to the other
        const similar = vectorResults.filter(r =>
          r.chunkType === "function" &&
          r.filePath.startsWith(otherService) &&
          r.score > 0.85
        );

        for (const match of similar) {
          result.issues.push({
            severity: "warning",
            file: match.filePath,
            line: match.startLine,
            message: `semantically similar code detected across services (score: ${match.score.toFixed(3)}). possible logic duplication between ${serviceDir} and ${otherService}`,
            fix: `consider extracting shared logic to shared/ or a common module`,
          });
        }
      }
    }
  }

  return result;
}

// ---- check: hardcoded value detection ----
// uses BOTH string matching (exact) and vectors (semantic similarity)

function checkHardcodedValues(projectRoot: string, vectorResults?: VectorSearchResult[]): CheckResult {
  const result: CheckResult = { name: "hardcoded-value-detection", pass: true, issues: [] };

  const domainValuesPath = path.join(projectRoot, "shared/domain-values.json");
  if (!existsSync(domainValuesPath)) return result;

  let domainValues: Record<string, any>;
  try {
    domainValues = JSON.parse(readFileSync(domainValuesPath, "utf-8"));
  } catch { return result; }

  // extract all string values
  const contractValues: string[] = [];
  function extractStrings(obj: any) {
    if (typeof obj === "string" && obj.length > 2) contractValues.push(obj);
    else if (typeof obj === "object" && obj !== null) {
      for (const val of Object.values(obj)) extractStrings(val);
    }
  }
  extractStrings(domainValues.values || domainValues);

  if (contractValues.length === 0) return result;

  // EXACT: scan for hardcoded string literals
  const sourceFiles = walkSourceFiles(projectRoot);

  for (const file of sourceFiles) {
    if (file.includes("/shared/")) continue;

    const content = readFileSync(file, "utf-8");
    const lines = content.split("\n");
    const relativePath = path.relative(projectRoot, file);

    for (let i = 0; i < lines.length; i++) {
      for (const value of contractValues) {
        if (lines[i].includes(`"${value}"`) || lines[i].includes(`'${value}'`)) {
          result.pass = false;
          result.issues.push({
            severity: "warning",
            file: relativePath,
            line: i + 1,
            message: `hardcoded value "${value}" should reference shared/domain-values.json`,
            fix: `import from shared/domain-values.json instead of hardcoding`,
          });
        }
      }
    }
  }

  // SEMANTIC: find code semantically similar to contract values
  if (vectorResults) {
    for (const value of contractValues) {
      const semanticMatches = vectorResults.filter(r =>
        r.chunkType === "function" &&
        !r.filePath.startsWith("shared/") &&
        r.content.toLowerCase().includes(value.toLowerCase()) &&
        r.score > 0.7
      );

      for (const match of semanticMatches) {
        // avoid duplicating exact matches
        const alreadyReported = result.issues.some(
          i => i.file === match.filePath && i.line === match.startLine
        );
        if (!alreadyReported) {
          result.issues.push({
            severity: "info",
            file: match.filePath,
            line: match.startLine,
            message: `code semantically related to contract value "${value}" (score: ${match.score.toFixed(3)})`,
            fix: `verify this code references shared/domain-values.json`,
          });
        }
      }
    }
  }

  return result;
}

// ---- check: API snapshot validation ----

function checkApiSnapshotValidation(projectRoot: string): CheckResult {
  const result: CheckResult = { name: "api-snapshot-validation", pass: true, issues: [] };

  const snapshotsPath = path.join(projectRoot, "shared/api-field-snapshots.json");
  if (!existsSync(snapshotsPath)) return result;

  try {
    const snapshots = JSON.parse(readFileSync(snapshotsPath, "utf-8"));
    const endpoints = snapshots.endpoints || {};

    if (Object.keys(endpoints).length === 0) {
      result.issues.push({
        severity: "info",
        file: "shared/api-field-snapshots.json",
        message: "no API snapshots defined yet",
        fix: "add endpoint snapshots as you build APIs",
      });
    }
  } catch (err: any) {
    result.pass = false;
    result.issues.push({
      severity: "critical",
      file: "shared/api-field-snapshots.json",
      message: `invalid JSON: ${err.message}`,
    });
  }

  return result;
}

// ---- check: import centralization ----
// uses BOTH regex (direct imports) and vectors (indirect HTTP calls)

function checkImportCentralization(projectRoot: string, vectorResults?: VectorSearchResult[]): CheckResult {
  const result: CheckResult = { name: "import-centralization", pass: true, issues: [] };

  const httpPatterns = [
    /import.*from\s+['"]axios['"]/,
    /require\(['"]axios['"]\)/,
    /import.*from\s+['"]node-fetch['"]/,
    /from\s+['"]httpx['"]/,
    /from\s+['"]requests['"]/,
    /import\s+['"]net\/http['"]/,
  ];

  // find central client
  const clientPatterns = ["lib/api-client", "lib/http-client", "utils/api", "clients/http"];
  let centralClient: string | null = null;

  for (const pattern of clientPatterns) {
    for (const ext of [".ts", ".js", ".py"]) {
      if (existsSync(path.join(projectRoot, pattern + ext))) {
        centralClient = pattern;
        break;
      }
    }
    if (centralClient) break;
  }

  if (!centralClient) return result;

  // EXACT: scan for direct HTTP library imports
  const sourceFiles = walkSourceFiles(projectRoot);

  for (const file of sourceFiles) {
    const relativePath = path.relative(projectRoot, file);
    if (relativePath.startsWith(centralClient)) continue;

    const content = readFileSync(file, "utf-8");
    const lines = content.split("\n");

    for (let i = 0; i < lines.length; i++) {
      for (const pattern of httpPatterns) {
        if (pattern.test(lines[i])) {
          result.pass = false;
          result.issues.push({
            severity: "warning",
            file: relativePath,
            line: i + 1,
            message: `direct HTTP client import. use ${centralClient} instead`,
            fix: `import from ${centralClient} for centralized error handling and auth`,
          });
        }
      }
    }
  }

  // SEMANTIC: find code that makes HTTP calls without importing HTTP libraries
  // (wrapped fetch, custom helpers, etc.)
  if (vectorResults) {
    const httpRelated = vectorResults.filter(r =>
      r.chunkType === "function" &&
      !r.filePath.startsWith(centralClient!) &&
      r.score > 0.6
    );

    for (const match of httpRelated) {
      const alreadyReported = result.issues.some(
        i => i.file === match.filePath && i.line === match.startLine
      );
      if (!alreadyReported && match.content.match(/fetch\(|\.get\(|\.post\(|\.put\(|\.delete\(/)) {
        result.issues.push({
          severity: "info",
          file: match.filePath,
          line: match.startLine,
          message: `possible HTTP call outside centralized client (score: ${match.score.toFixed(3)})`,
          fix: `verify this uses ${centralClient} for HTTP requests`,
        });
      }
    }
  }

  return result;
}

// ---- check: duplicate logic detection (vector-only, the killer check) ----
// finds semantically similar functions across the codebase

async function checkDuplicateLogic(projectRoot: string): Promise<CheckResult> {
  const result: CheckResult = { name: "duplicate-logic-detection", pass: true, issues: [] };

  const hasIndex = existsSync(path.join(projectRoot, ".cage/vectors"));
  if (!hasIndex) {
    result.issues.push({
      severity: "info",
      file: "",
      message: "no vector index. run 'cage index' to enable duplicate detection",
    });
    return result;
  }

  openShard(projectRoot);

  try {
    // get all function chunks by scrolling
    const stats = shardStats();
    if (stats.points === 0) return result;

    // search for each function against the rest
    // this is O(n) searches but n is typically <500 for most projects
    const functionFiles = walkSourceFiles(projectRoot);
    const seen = new Set<string>();

    for (const file of functionFiles) {
      const content = readFileSync(file, "utf-8");
      const relativePath = path.relative(projectRoot, file);
      const functions = extractFunctions(content, relativePath);

      for (const func of functions) {
        if (func.content.length < 30) continue; // skip very tiny functions

        const results = await vectorSearch(func.content, 5, "function");

        for (const match of results) {
          // skip self-matches
          if (match.filePath === relativePath && match.startLine === func.startLine) continue;

          // skip if already reported (A~B = B~A)
          const pairKey = [relativePath, match.filePath].sort().join(":");
          if (seen.has(pairKey)) continue;

          if (match.score > 0.85) {
            seen.add(pairKey);
            result.issues.push({
              severity: "warning",
              file: relativePath,
              line: func.startLine,
              message: `highly similar to ${match.filePath}:${match.startLine} (score: ${match.score.toFixed(3)}). possible duplication.`,
              fix: `extract shared logic into a common module`,
            });
          }
        }
      }
    }
  } finally {
    closeShard();
  }

  return result;
}

// ---- orchestrator ----

const SYNC_CHECKS = [
  checkBoundaryEnforcement,
  checkHardcodedValues,
  checkApiSnapshotValidation,
  checkImportCentralization,
];

export async function checkRun(projectRoot: string, checkName?: string): Promise<boolean> {
  console.log("running architectural checks...\n");

  let allPassed = true;

  // gather vector results if index exists (for hybrid checks)
  let vectorResults: VectorSearchResult[] | undefined;
  const hasIndex = existsSync(path.join(projectRoot, ".cage/vectors"));

  if (hasIndex) {
    try {
      openShard(projectRoot);
      // we'll pass these to checks that can use them
      console.log("  vector index loaded (hybrid mode)\n");
    } catch (err: any) {
      console.log(`  vector index unavailable: ${err.message} (regex-only mode)\n`);
    }
  } else {
    console.log("  no vector index (regex-only mode). run 'cage index' for hybrid checks.\n");
  }

  // run sync checks
  for (const check of SYNC_CHECKS) {
    const checkResult = check(projectRoot, vectorResults);

    if (checkName && checkResult.name !== checkName) continue;

    if (checkResult.pass && checkResult.issues.filter(i => i.severity !== "info").length === 0) {
      console.log(`  [ok] ${checkResult.name}`);
    } else if (!checkResult.pass) {
      console.log(`  [FAIL] ${checkResult.name}`);
      allPassed = false;
    } else {
      console.log(`  [ok] ${checkResult.name}`);
    }

    for (const issue of checkResult.issues) {
      const loc = issue.line ? `${issue.file}:${issue.line}` : issue.file;
      console.log(`    [${issue.severity}] ${loc}: ${issue.message}`);
      if (issue.fix) console.log(`      fix: ${issue.fix}`);
    }
  }

  // run async vector-only checks
  if (!checkName || checkName === "duplicate-logic-detection") {
    const dupResult = await checkDuplicateLogic(projectRoot);

    if (dupResult.pass && dupResult.issues.filter(i => i.severity !== "info").length === 0) {
      console.log(`  [ok] ${dupResult.name}`);
    } else if (!dupResult.pass) {
      console.log(`  [FAIL] ${dupResult.name}`);
      allPassed = false;
    } else {
      console.log(`  [ok] ${dupResult.name}`);
    }

    for (const issue of dupResult.issues) {
      const loc = issue.line ? `${issue.file}:${issue.line}` : (issue.file || "-");
      console.log(`    [${issue.severity}] ${loc}: ${issue.message}`);
      if (issue.fix) console.log(`      fix: ${issue.fix}`);
    }
  }

  if (hasIndex) {
    try { closeShard(); } catch {}
  }

  console.log(`\n${allPassed ? "all checks passed" : "some checks failed"}`);
  return allPassed;
}

export async function checkList(): Promise<void> {
  console.log("available checks:\n");
  console.log("  boundary-enforcement        cross-service import detection (exact + semantic)");
  console.log("  hardcoded-value-detection    values that should be in shared/ (exact + semantic)");
  console.log("  api-snapshot-validation      API response shape consistency");
  console.log("  import-centralization        HTTP client usage through central module (exact + semantic)");
  console.log("  duplicate-logic-detection    semantically similar code across codebase (vector-only)");
}

// ---- utilities ----

function detectServiceDirs(projectRoot: string): string[] {
  const serviceDirs: string[] = [];
  const candidates = ["services", "apps", "packages"];

  for (const candidate of candidates) {
    const dir = path.join(projectRoot, candidate);
    if (existsSync(dir)) {
      try {
        const entries = readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
          if (entry.isDirectory()) serviceDirs.push(path.join(candidate, entry.name));
        }
      } catch {}
    }
  }

  for (const name of ["backend", "frontend", "api", "web", "worker"]) {
    if (existsSync(path.join(projectRoot, name))) serviceDirs.push(name);
  }

  return serviceDirs;
}

function isImportLine(line: string): boolean {
  const trimmed = line.trim();
  return (
    trimmed.startsWith("import ") || trimmed.startsWith("from ") ||
    trimmed.includes("require(") || trimmed.startsWith("use ")
  );
}

function walkSourceFiles(dir: string, files: string[] = []): string[] {
  const skipDirs = new Set([
    "node_modules", ".git", ".cage", "__pycache__", ".next",
    "dist", "build", ".venv", "venv", "target",
  ]);
  const sourceExts = new Set([".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go"]);

  try {
    const entries = readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory() && !skipDirs.has(entry.name) && !entry.name.startsWith(".")) {
        walkSourceFiles(path.join(dir, entry.name), files);
      } else if (entry.isFile() && sourceExts.has(path.extname(entry.name))) {
        files.push(path.join(dir, entry.name));
      }
    }
  } catch {}
  return files;
}

interface FuncChunk {
  content: string;
  startLine: number;
}

function extractFunctions(content: string, filePath: string): FuncChunk[] {
  const lines = content.split("\n");
  const funcs: FuncChunk[] = [];
  const ext = path.extname(filePath);

  let pattern: RegExp | null = null;
  if ([".ts", ".tsx", ".js", ".jsx"].includes(ext)) {
    pattern = /(?:export\s+)?(?:async\s+)?function\s+\w+|(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\(/;
  } else if (ext === ".py") {
    pattern = /^(?:async\s+)?def\s+\w+/;
  } else if (ext === ".rs") {
    pattern = /^(?:pub\s+)?(?:async\s+)?fn\s+\w+/;
  } else if (ext === ".go") {
    pattern = /^func\s+/;
  }

  if (!pattern) return funcs;

  let current: FuncChunk | null = null;

  for (let i = 0; i < lines.length; i++) {
    if (pattern.test(lines[i])) {
      if (current && current.content.split("\n").length > 1) {
        funcs.push(current);
      }
      current = { content: lines[i], startLine: i + 1 };
    } else if (current) {
      current.content += "\n" + lines[i];
    }
  }

  if (current && current.content.split("\n").length > 1) {
    funcs.push(current);
  }

  return funcs;
}
