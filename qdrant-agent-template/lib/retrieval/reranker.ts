import { env } from "@/lib/shared/env";
import { logger } from "@/lib/shared/logger";
import type { RerankResult, RerankParams } from "./types";

/**
 * Reranker adapter interface
 */
interface RerankerAdapter {
  rerank(params: RerankParams): Promise<RerankResult[]>;
}

/**
 * Cohere Reranker
 */
class CohereReranker implements RerankerAdapter {
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async rerank(params: RerankParams): Promise<RerankResult[]> {
    const { query, documents, topN = 10 } = params;

    const response = await fetch("https://api.cohere.com/v2/rerank", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: "rerank-v3.5",
        query,
        documents,
        top_n: topN,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Cohere rerank failed: ${response.status} - ${error}`);
    }

    const data = await response.json();

    return data.results.map((r: { index: number; relevance_score: number }) => ({
      index: r.index,
      score: r.relevance_score,
    }));
  }
}

/**
 * Jina Reranker
 */
class JinaReranker implements RerankerAdapter {
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async rerank(params: RerankParams): Promise<RerankResult[]> {
    const { query, documents, topN = 10 } = params;

    const response = await fetch("https://api.jina.ai/v1/rerank", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: "jina-reranker-v2-base-multilingual",
        query,
        documents,
        top_n: topN,
        return_documents: false,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Jina rerank failed: ${response.status} - ${error}`);
    }

    const data = await response.json();

    return data.results.map((r: { index: number; relevance_score: number }) => ({
      index: r.index,
      score: r.relevance_score,
    }));
  }
}

/**
 * Create reranker based on configuration
 */
export function createReranker(): RerankerAdapter {
  const provider = env.RERANKER_PROVIDER;

  if (provider === "cohere" && env.COHERE_API_KEY) {
    logger.debug("Using Cohere reranker");
    return new CohereReranker(env.COHERE_API_KEY);
  }

  if (provider === "jina" && env.JINA_API_KEY) {
    logger.debug("Using Jina reranker");
    return new JinaReranker(env.JINA_API_KEY);
  }

  throw new Error(
    `No API key configured for reranker provider: ${provider}`
  );
}

/**
 * Rerank chunks using the configured reranker
 */
export async function rerankChunks(
  query: string,
  chunks: Array<{ id: string; text: string; [key: string]: unknown }>,
  topN: number = 10
): Promise<Array<{ id: string; score: number; originalIndex: number }>> {
  if (chunks.length === 0) {
    return [];
  }

  const reranker = createReranker();
  const documents = chunks.map((c) => c.text);

  logger.debug("Reranking", { numDocs: documents.length, topN });

  const results = await reranker.rerank({
    query,
    documents,
    topN,
  });

  return results.map((r) => ({
    id: chunks[r.index].id,
    score: r.score,
    originalIndex: r.index,
  }));
}
