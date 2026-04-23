import { getQdrantClient } from "./client";
import { COLLECTIONS } from "./collections";
import { embedder } from "./embedder";
import { logger } from "@/lib/shared/logger";
import type {
  SearchParams,
  SearchFilters,
  RetrievedChunk,
  ChunkPayload,
} from "./types";

/**
 * Build Qdrant filter from search filters
 */
function buildFilter(filters?: SearchFilters) {
  if (!filters) return undefined;

  const must: unknown[] = [];

  if (filters.source?.length) {
    must.push({
      key: "source",
      match: { any: filters.source },
    });
  }

  if (filters.tags?.length) {
    must.push({
      key: "tags",
      match: { any: filters.tags },
    });
  }

  if (filters.accessScope) {
    must.push({
      key: "access_scope",
      match: { value: filters.accessScope },
    });
  }

  if (filters.docId) {
    must.push({
      key: "doc_id",
      match: { value: filters.docId },
    });
  }

  if (filters.timeRange) {
    if (filters.timeRange.start) {
      must.push({
        key: "created_at",
        range: { gte: filters.timeRange.start },
      });
    }
    if (filters.timeRange.end) {
      must.push({
        key: "created_at",
        range: { lte: filters.timeRange.end },
      });
    }
  }

  return must.length > 0 ? { must } : undefined;
}

/**
 * Single-query search
 */
export async function search(params: SearchParams): Promise<RetrievedChunk[]> {
  const client = getQdrantClient();
  const { query, mode, topK, filters, fusionMethod = "rrf", rrfK = 60 } = params;

  const filter = buildFilter(filters);
  
  // Get embeddings
  const dense = await embedder.embedQuery(query);
  const sparse = embedder.getSparseVector(query);

  logger.debug("Searching", { mode, topK, hasFilters: !!filters });

  let results;

  if (mode === "dense") {
    results = await client.query(COLLECTIONS.CORPUS_CHUNKS, {
      query: dense,
      using: "dense",
      limit: topK,
      filter,
      with_payload: true,
    });
  } else if (mode === "sparse") {
    results = await client.query(COLLECTIONS.CORPUS_CHUNKS, {
      query: sparse,
      using: "sparse",
      limit: topK,
      filter,
      with_payload: true,
    });
  } else {
    // Hybrid search with fusion
    results = await client.query(COLLECTIONS.CORPUS_CHUNKS, {
      prefetch: [
        {
          query: dense,
          using: "dense",
          limit: topK * 2,
        },
        {
          query: sparse,
          using: "sparse",
          limit: topK * 2,
        },
      ],
      query:
        fusionMethod === "dbsf"
          ? { fusion: "dbsf" }
          : { rrf: { k: rrfK } },
      limit: topK,
      filter,
      with_payload: true,
    });
  }

  return (results.points || []).map((point) => ({
    id: String(point.id),
    score: point.score ?? 0,
    payload: point.payload as unknown as ChunkPayload,
  }));
}

/**
 * Search for multiple queries (for multi-query retrieval)
 * Returns results tagged with query index
 */
export async function searchMultiple(
  queries: Array<{ text: string; filters?: SearchFilters }>,
  mode: "dense" | "sparse" | "hybrid",
  topKPerQuery: number
): Promise<RetrievedChunk[]> {
  const allResults: RetrievedChunk[] = [];

  // Run searches in parallel
  const searchPromises = queries.map(async (q, index) => {
    const results = await search({
      query: q.text,
      mode,
      topK: topKPerQuery,
      filters: q.filters,
    });
    return results.map((r) => ({ ...r, queryIndex: index }));
  });

  const resultSets = await Promise.all(searchPromises);
  for (const results of resultSets) {
    allResults.push(...results);
  }

  return allResults;
}

/**
 * Get chunk by ID
 */
export async function getChunkById(id: string): Promise<RetrievedChunk | null> {
  const client = getQdrantClient();

  try {
    const results = await client.retrieve(COLLECTIONS.CORPUS_CHUNKS, {
      ids: [id],
      with_payload: true,
    });

    if (results.length === 0) return null;

    const point = results[0];
    return {
      id: String(point.id),
      score: 1,
      payload: point.payload as unknown as ChunkPayload,
    };
  } catch {
    return null;
  }
}

/**
 * Get multiple chunks by IDs
 */
export async function getChunksByIds(ids: string[]): Promise<RetrievedChunk[]> {
  const client = getQdrantClient();

  const results = await client.retrieve(COLLECTIONS.CORPUS_CHUNKS, {
    ids,
    with_payload: true,
  });

  return results.map((point) => ({
    id: String(point.id),
    score: 1,
    payload: point.payload as unknown as ChunkPayload,
  }));
}
