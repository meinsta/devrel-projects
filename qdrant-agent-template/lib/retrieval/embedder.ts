import { CohereClient } from "cohere-ai";
import { env } from "@/lib/shared/env";

/**
 * Cohere Embedder
 * Uses Cohere API for dense embeddings
 * Uses simple BM25 approximation for sparse vectors
 */

// Cohere embed-multilingual-v2.0 produces 768-dimensional vectors
export const COHERE_EMBED_SIZE = 768;
export const COHERE_EMBED_MODEL = "embed-multilingual-v2.0";

const cohere = new CohereClient({
  token: env.COHERE_API_KEY,
});

/**
 * Generate dense embedding using Cohere
 */
export async function embedText(text: string): Promise<number[]> {
  const response = await cohere.embed({
    texts: [text],
    model: COHERE_EMBED_MODEL,
    inputType: "search_document",
  });
  
  // Response is EmbedResponse with embeddings as number[][]
  const embeddings = response.embeddings as number[][];
  return embeddings[0];
}

/**
 * Generate dense embeddings for multiple texts (batched)
 */
export async function embedTexts(texts: string[]): Promise<number[][]> {
  if (texts.length === 0) return [];
  
  // Cohere has a limit of 96 texts per request
  const batchSize = 96;
  const allEmbeddings: number[][] = [];
  
  for (let i = 0; i < texts.length; i += batchSize) {
    const batch = texts.slice(i, i + batchSize);
    const response = await cohere.embed({
      texts: batch,
      model: COHERE_EMBED_MODEL,
      inputType: "search_document",
    });
    const embeddings = response.embeddings as number[][];
    allEmbeddings.push(...embeddings);
  }
  
  return allEmbeddings;
}

/**
 * Generate query embedding (uses search_query input type)
 */
export async function embedQuery(text: string): Promise<number[]> {
  const response = await cohere.embed({
    texts: [text],
    model: COHERE_EMBED_MODEL,
    inputType: "search_query",
  });
  const embeddings = response.embeddings as number[][];
  return embeddings[0];
}

/**
 * Simple BM25-style sparse vector generation
 * This is a basic implementation - in production you'd want proper BM25
 */
export function generateSparseVector(text: string): { indices: number[]; values: number[] } {
  const words = text.toLowerCase().split(/\s+/).filter(w => w.length > 2);
  const termFreq = new Map<string, number>();
  
  for (const word of words) {
    termFreq.set(word, (termFreq.get(word) || 0) + 1);
  }
  
  // Use hash of word as index (simple approach)
  const indices: number[] = [];
  const values: number[] = [];
  
  for (const [word, freq] of termFreq) {
    // Simple hash function to get index
    let hash = 0;
    for (let i = 0; i < word.length; i++) {
      hash = ((hash << 5) - hash) + word.charCodeAt(i);
      hash = hash & hash; // Convert to 32bit integer
    }
    indices.push(Math.abs(hash) % 100000); // Cap at 100k dimensions
    values.push(Math.log(1 + freq)); // Log TF
  }
  
  return { indices, values };
}

/**
 * Embedder class for convenient access
 */
export class CohereEmbedder {
  /**
   * Get dense vector for document indexing
   */
  async embedDocument(text: string): Promise<number[]> {
    return embedText(text);
  }

  /**
   * Get dense vectors for multiple documents
   */
  async embedDocuments(texts: string[]): Promise<number[][]> {
    return embedTexts(texts);
  }

  /**
   * Get dense vector for query
   */
  async embedQuery(text: string): Promise<number[]> {
    return embedQuery(text);
  }

  /**
   * Get sparse vector
   */
  getSparseVector(text: string): { indices: number[]; values: number[] } {
    return generateSparseVector(text);
  }
}

// Default embedder instance
export const embedder = new CohereEmbedder();
