// vector-engine.ts: Qdrant Edge (in-process) + Jina Code v2 embeddings
//
// no server, no daemon, no port. qdrant-edge runs as a native library
// inside cage-core's process. data persists to .cage/vectors/

import { QdrantEdge, type EdgeConfig, type PointInput, type SearchResult } from "qdrant-edge";
import { pipeline, env } from "@huggingface/transformers";
import { existsSync, mkdirSync } from "fs";
import path from "path";

const EMBEDDING_MODEL = "jinaai/jina-embeddings-v2-base-code";
const EMBEDDING_DIM = 768;
const VECTOR_NAME = "code";

let shard: QdrantEdge | null = null;
let embedder: any = null;

// ---- shard lifecycle ----

export function openShard(projectRoot: string): QdrantEdge {
  if (shard) return shard;

  const vectorDir = path.join(projectRoot, ".cage", "vectors");
  mkdirSync(vectorDir, { recursive: true });

  const config: EdgeConfig = {
    path: vectorDir,
    vectorSize: EMBEDDING_DIM,
    distance: "cosine",
    vectorName: VECTOR_NAME,
  };

  if (existsSync(path.join(vectorDir, "segment_manifest.json"))) {
    // reopen existing shard
    shard = QdrantEdge.reopen(vectorDir);
  } else {
    // create new shard
    shard = QdrantEdge.open(config);
  }

  return shard;
}

export function closeShard(): void {
  if (shard) {
    shard.flush();
    shard.close();
    shard = null;
  }
}

// ---- embedding generation ----

async function getEmbedder() {
  if (!embedder) {
    console.log("  loading jina-code-v2 model (first run downloads ~300MB)...");
    embedder = await pipeline("feature-extraction", EMBEDDING_MODEL, {
      dtype: "fp32",
    });
    console.log("  model loaded");
  }
  return embedder;
}

export async function embed(texts: string[]): Promise<number[][]> {
  const model = await getEmbedder();
  const results: number[][] = [];

  const BATCH_SIZE = 16;
  for (let i = 0; i < texts.length; i += BATCH_SIZE) {
    const batch = texts.slice(i, i + BATCH_SIZE);
    // truncate to jina-code-v2 max (8192 tokens)
    const truncated = batch.map(t => t.slice(0, 8000));

    const output = await model(truncated, { pooling: "mean", normalize: true });
    const vectors = output.tolist();
    results.push(...vectors);

    if (texts.length > BATCH_SIZE) {
      const pct = Math.min(100, Math.round(((i + batch.length) / texts.length) * 100));
      process.stdout.write(`\r  embedding... ${pct}%`);
    }
  }

  if (texts.length > BATCH_SIZE) {
    process.stdout.write("\n");
  }

  return results;
}

// ---- upsert ----

export interface CodeChunk {
  id: number;
  filePath: string;
  content: string;
  startLine: number;
  endLine: number;
  chunkType: string;
  language: string;
}

export async function upsertChunks(chunks: CodeChunk[]): Promise<void> {
  if (!shard) throw new Error("shard not open");
  if (chunks.length === 0) return;

  // generate embeddings
  const texts = chunks.map(c => `${c.filePath}\n${c.content}`);
  console.log(`  embedding ${texts.length} chunks...`);
  const vectors = await embed(texts);

  // build points
  const points: PointInput[] = chunks.map((chunk, i) => ({
    id: chunk.id,
    vector: vectors[i],
    payload: JSON.stringify({
      filePath: chunk.filePath,
      content: chunk.content.slice(0, 2000), // cap payload size
      startLine: chunk.startLine,
      endLine: chunk.endLine,
      chunkType: chunk.chunkType,
      language: chunk.language,
    }),
  }));

  // batch upsert
  const BATCH = 100;
  for (let i = 0; i < points.length; i += BATCH) {
    shard.upsert(points.slice(i, i + BATCH));
  }

  shard.flush();
  console.log(`  upserted ${points.length} vectors`);
}

// ---- search ----

export interface VectorSearchResult {
  filePath: string;
  content: string;
  startLine: number;
  endLine: number;
  chunkType: string;
  language: string;
  score: number;
}

export async function vectorSearch(
  query: string,
  limit: number = 10,
  chunkTypeFilter?: string,
): Promise<VectorSearchResult[]> {
  if (!shard) throw new Error("shard not open");

  const [queryVector] = await embed([query]);

  let results: SearchResult[];
  if (chunkTypeFilter) {
    const filter = JSON.stringify({
      must: [{ key: "chunkType", match: { value: chunkTypeFilter } }],
    });
    results = shard.searchWithFilter(queryVector, filter, limit, true);
  } else {
    results = shard.search(queryVector, limit, true);
  }

  return results.map(r => {
    const payload = r.payload ? JSON.parse(r.payload) : {};
    return {
      filePath: payload.filePath || "",
      content: payload.content || "",
      startLine: payload.startLine || 0,
      endLine: payload.endLine || 0,
      chunkType: payload.chunkType || "",
      language: payload.language || "",
      score: r.score,
    };
  });
}

// ---- stats ----

export function shardStats(): { segments: number; points: number } {
  if (!shard) throw new Error("shard not open");
  const info = shard.info();
  return { segments: info.segmentsCount, points: info.pointsCount };
}

// ---- delete stale points ----

export function deletePoints(ids: number[]): number {
  if (!shard) throw new Error("shard not open");
  const deleted = shard.delete(ids);
  shard.flush();
  return deleted;
}

// ---- deterministic ID from string ----

export function hashToId(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash + s.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}
