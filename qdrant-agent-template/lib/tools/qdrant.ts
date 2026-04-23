import { search } from "@/lib/retrieval/search";
import { rerankChunks } from "@/lib/retrieval/reranker";
import { logger } from "@/lib/shared/logger";
import {
  QdrantSearchInputSchema,
  QdrantSearchResultSchema,
  type ToolDefinition,
  type QdrantSearchInput,
  type QdrantSearchResult,
} from "./types";

/**
 * Execute Qdrant knowledge search
 * Wraps the existing retrieval system as a tool
 */
export async function executeQdrantSearch(
  input: QdrantSearchInput
): Promise<QdrantSearchResult> {
  const startTime = Date.now();

  try {
    // Execute search using existing retrieval system
    const results = await search({
      query: input.query,
      mode: input.mode,
      topK: input.topK,
      filters: input.filters ? {
        source: input.filters.source ? [input.filters.source] : undefined,
        tags: input.filters.tags,
        docId: input.filters.docId,
      } : undefined,
    });

    // Optionally rerank for quality
    let finalResults = results;
    if (results.length > 10) {
      const reranked = await rerankChunks(
        input.query,
        results.slice(0, 30).map((c) => ({ id: c.id, text: c.payload.text })),
        Math.min(input.topK, 20)
      );

      finalResults = reranked.map((r) => ({
        ...results[r.originalIndex],
        score: r.score,
      }));
    }

    logger.info("Qdrant search completed", {
      query: input.query.slice(0, 50),
      mode: input.mode,
      latencyMs: Date.now() - startTime,
      resultCount: finalResults.length,
    });

    return {
      chunks: finalResults.map((c) => ({
        id: c.id,
        text: c.payload.text,
        score: c.score,
        metadata: {
          docId: c.payload.doc_id,
          title: c.payload.title,
          source: c.payload.source,
          url: c.payload.url,
        },
      })),
      totalFound: results.length,
    };
  } catch (error) {
    logger.error("Qdrant search failed", error as Error);
    throw error;
  }
}

/**
 * Qdrant Knowledge Search Tool Definition
 */
export const qdrantSearchTool: ToolDefinition<QdrantSearchInput, QdrantSearchResult> = {
  name: "qdrant_search",
  description: `Search the knowledge base using vector similarity. Use this when:
- The query is about topics covered in your documents/knowledge base
- You need to find specific information from ingested content
- Historical or static information that doesn't require real-time data
Supports modes: "dense" (semantic), "sparse" (keyword), "hybrid" (both)`,
  category: "knowledge",
  inputSchema: QdrantSearchInputSchema,
  outputSchema: QdrantSearchResultSchema,
  execute: executeQdrantSearch,
};

/**
 * Get Qdrant tool for Vercel AI SDK tool calling
 */
export function getQdrantToolForAI() {
  return {
    qdrant_search: {
      description: qdrantSearchTool.description,
      parameters: QdrantSearchInputSchema,
      execute: async (input: QdrantSearchInput) => {
        const result = await executeQdrantSearch(input);
        return {
          documents: result.chunks.map((c, i) => ({
            index: i + 1,
            id: c.id,
            relevanceScore: c.score.toFixed(3),
            title: c.metadata.title,
            content: c.text,
            source: c.metadata.source,
          })),
          totalFound: result.totalFound,
        };
      },
    },
  };
}
