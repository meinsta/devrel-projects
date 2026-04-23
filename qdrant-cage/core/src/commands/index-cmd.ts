import { existsSync, readFileSync, writeFileSync, readdirSync, mkdirSync } from "fs";
import { execSync } from "child_process";
import path from "path";
import crypto from "crypto";
import {
  openShard, closeShard, upsertChunks, vectorSearch,
  shardStats, hashToId, type CodeChunk, type VectorSearchResult,
} from "../vector-engine";

interface IndexMeta {
  lastIndexed: string;
  commit?: string;
  fileHashes: Record<string, string>;
  totalChunks: number;
  totalFiles: number;
}

const SUPPORTED_EXTENSIONS: Record<string, string> = {
  ".ts": "typescript", ".tsx": "typescript",
  ".js": "javascript", ".jsx": "javascript",
  ".py": "python", ".rs": "rust", ".go": "go",
  ".java": "java", ".rb": "ruby", ".php": "php",
  ".swift": "swift", ".kt": "kotlin", ".scala": "scala",
  ".ex": "elixir", ".exs": "elixir",
};

const SKIP_DIRS = new Set([
  "node_modules", ".git", ".cage", "__pycache__", ".next",
  "dist", "build", ".venv", "venv", "target", ".tox",
  ".mypy_cache", ".pytest_cache", "coverage",
]);

function fileHash(content: string): string {
  return crypto.createHash("md5").update(content).digest("hex");
}

function walkFiles(dir: string, files: string[] = []): string[] {
  try {
    const entries = readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) {
        if (!SKIP_DIRS.has(entry.name) && !entry.name.startsWith(".")) {
          walkFiles(path.join(dir, entry.name), files);
        }
      } else if (entry.isFile()) {
        const ext = path.extname(entry.name);
        if (SUPPORTED_EXTENSIONS[ext]) {
          files.push(path.join(dir, entry.name));
        }
      }
    }
  } catch {}
  return files;
}

function getFunctionPattern(language: string): RegExp | null {
  switch (language) {
    case "typescript":
    case "javascript":
      return /(?:export\s+)?(?:async\s+)?function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(/;
    case "python":
      return /^(?:async\s+)?def\s+(\w+)/;
    case "rust":
      return /^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)/;
    case "go":
      return /^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)/;
    default:
      return null;
  }
}

function chunkFile(filePath: string, content: string, language: string): CodeChunk[] {
  const chunks: CodeChunk[] = [];
  const lines = content.split("\n");

  // file-level chunk
  chunks.push({
    id: hashToId(`file:${filePath}`),
    filePath,
    content: content.slice(0, 2000),
    startLine: 1,
    endLine: lines.length,
    chunkType: "file",
    language,
  });

  // import-level chunk
  const importLines: string[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (
      trimmed.startsWith("import ") || trimmed.startsWith("from ") ||
      (trimmed.startsWith("const ") && trimmed.includes("require(")) ||
      trimmed.startsWith("use ") // rust
    ) {
      importLines.push(trimmed);
    }
  }
  if (importLines.length > 0) {
    chunks.push({
      id: hashToId(`import:${filePath}`),
      filePath,
      content: importLines.join("\n"),
      startLine: 1,
      endLine: 1,
      chunkType: "import",
      language,
    });
  }

  // function-level chunks
  const functionPattern = getFunctionPattern(language);
  if (functionPattern) {
    let currentFunc: { startLine: number; lines: string[] } | null = null;
    let funcCount = 0;

    for (let i = 0; i < lines.length; i++) {
      const match = lines[i].match(functionPattern);
      if (match) {
        if (currentFunc && currentFunc.lines.length > 1) {
          chunks.push({
            id: hashToId(`func:${filePath}:${funcCount}`),
            filePath,
            content: currentFunc.lines.join("\n"),
            startLine: currentFunc.startLine,
            endLine: i,
            chunkType: "function",
            language,
          });
          funcCount++;
        }
        currentFunc = { startLine: i + 1, lines: [lines[i]] };
      } else if (currentFunc) {
        currentFunc.lines.push(lines[i]);
      }
    }

    if (currentFunc && currentFunc.lines.length > 1) {
      chunks.push({
        id: hashToId(`func:${filePath}:${funcCount}`),
        filePath,
        content: currentFunc.lines.join("\n"),
        startLine: currentFunc.startLine,
        endLine: lines.length,
        chunkType: "function",
        language,
      });
    }
  }

  return chunks;
}

function chunkContracts(sharedDir: string): CodeChunk[] {
  const chunks: CodeChunk[] = [];
  if (!existsSync(sharedDir)) return chunks;

  const files = readdirSync(sharedDir).filter(f => f.endsWith(".json"));
  for (const file of files) {
    const filePath = path.join("shared", file);
    try {
      const content = readFileSync(path.join(sharedDir, file), "utf-8");
      const data = JSON.parse(content);

      for (const [key, value] of Object.entries(data)) {
        if (key.startsWith("_")) continue;
        chunks.push({
          id: hashToId(`contract:${filePath}:${key}`),
          filePath,
          content: `${key}: ${JSON.stringify(value, null, 2)}`,
          startLine: 1,
          endLine: 1,
          chunkType: "contract",
          language: "json",
        });
      }
    } catch {}
  }

  return chunks;
}

export async function index(projectRoot: string): Promise<void> {
  const absRoot = path.resolve(projectRoot);
  const cageDir = path.join(absRoot, ".cage");
  mkdirSync(cageDir, { recursive: true });

  const metaPath = path.join(cageDir, "index-meta.json");

  let existingMeta: IndexMeta | null = null;
  if (existsSync(metaPath)) {
    try { existingMeta = JSON.parse(readFileSync(metaPath, "utf-8")); } catch {}
  }

  console.log(`indexing ${absRoot}...\n`);

  const files = walkFiles(absRoot);
  console.log(`  found ${files.length} source files`);

  // compute hashes, find changed files
  const currentHashes: Record<string, string> = {};
  const changedFiles: string[] = [];

  for (const file of files) {
    const relativePath = path.relative(absRoot, file);
    const content = readFileSync(file, "utf-8");
    const hash = fileHash(content);
    currentHashes[relativePath] = hash;

    if (!existingMeta || existingMeta.fileHashes[relativePath] !== hash) {
      changedFiles.push(file);
    }
  }

  if (changedFiles.length === 0 && existingMeta) {
    console.log("  no changes since last index");
    return;
  }

  console.log(`  ${changedFiles.length} files changed`);

  // chunk
  const allChunks: CodeChunk[] = [];

  for (const file of changedFiles) {
    const relativePath = path.relative(absRoot, file);
    const content = readFileSync(file, "utf-8");
    const ext = path.extname(file);
    const language = SUPPORTED_EXTENSIONS[ext] || "unknown";
    allChunks.push(...chunkFile(relativePath, content, language));
  }

  allChunks.push(...chunkContracts(path.join(absRoot, "shared")));

  console.log(`  ${allChunks.length} chunks (${allChunks.filter(c => c.chunkType === "file").length} file, ${allChunks.filter(c => c.chunkType === "function").length} function, ${allChunks.filter(c => c.chunkType === "import").length} import, ${allChunks.filter(c => c.chunkType === "contract").length} contract)`);

  // open qdrant edge shard and upsert
  openShard(absRoot);

  try {
    await upsertChunks(allChunks);

    const stats = shardStats();
    console.log(`\n  qdrant edge: ${stats.points} points in ${stats.segments} segments`);
  } finally {
    closeShard();
  }

  // save meta
  let commit: string | undefined;
  try { commit = execSync("git rev-parse --short HEAD", { encoding: "utf-8", cwd: absRoot }).trim(); } catch {}

  const meta: IndexMeta = {
    lastIndexed: new Date().toISOString(),
    commit,
    fileHashes: currentHashes,
    totalChunks: allChunks.length,
    totalFiles: files.length,
  };
  writeFileSync(metaPath, JSON.stringify(meta, null, 2));

  console.log(`\nindex complete: ${allChunks.length} chunks from ${files.length} files`);
}

export async function search(query: string): Promise<void> {
  if (!query) {
    console.error("error: search query required");
    console.error("usage: cage-core search <query>");
    process.exit(1);
  }

  const absRoot = process.cwd();

  // check if index exists
  if (!existsSync(path.join(absRoot, ".cage/vectors"))) {
    console.error("no vector index found. run 'cage index' first");
    process.exit(1);
  }

  openShard(absRoot);

  try {
    console.log(`searching: "${query}"\n`);

    const results = await vectorSearch(query, 10);

    if (results.length === 0) {
      console.log("no results found");
      return;
    }

    for (const r of results) {
      const snippet = r.content.split("\n").slice(0, 3).join("\n");
      console.log(`  ${r.filePath}:${r.startLine} [${r.chunkType}] (score: ${r.score.toFixed(3)})`);
      console.log(`    ${snippet.replace(/\n/g, "\n    ")}`);
      console.log();
    }
  } finally {
    closeShard();
  }
}
