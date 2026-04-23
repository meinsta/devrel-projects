import { CohereClientV2 } from "cohere-ai";

const COHERE_API_KEY = process.env.COHERE_API_KEY!;

// Cohere embed-multilingual-v2.0 - matches existing wikipedia_multimodal collection
const EMBEDDING_MODEL = "embed-multilingual-v2.0";
const EMBEDDING_DIMENSIONS = 768;

let _client: CohereClientV2 | null = null;

function getClient(): CohereClientV2 {
  if (!_client) {
    _client = new CohereClientV2({ token: COHERE_API_KEY });
  }
  return _client;
}

/**
 * Generate dense embedding using Cohere (matches existing 35M collection)
 */
export async function embed(text: string): Promise<number[]> {
  const client = getClient();

  const response = await client.embed({
    model: EMBEDDING_MODEL,
    texts: [text],
    inputType: "search_query",
    embeddingTypes: ["float"],
  });

  const embeddings = response.embeddings;
  if (embeddings && "float" in embeddings && embeddings.float && embeddings.float.length > 0) {
    return embeddings.float[0];
  }

  throw new Error("Failed to get embedding from Cohere");
}

/**
 * Batch embed multiple texts in a single API call (more efficient)
 */
export async function embedBatch(texts: string[]): Promise<number[][]> {
  if (texts.length === 0) return [];
  if (texts.length === 1) return [await embed(texts[0])];

  const client = getClient();

  const response = await client.embed({
    model: EMBEDDING_MODEL,
    texts,
    inputType: "search_query",
    embeddingTypes: ["float"],
  });

  const embeddings = response.embeddings;
  if (embeddings && "float" in embeddings && embeddings.float && embeddings.float.length === texts.length) {
    return embeddings.float;
  }

  throw new Error("Failed to get batch embeddings from Cohere");
}

// Export configuration
export const EMBEDDING_CONFIG = {
  model: EMBEDDING_MODEL,
  dimensions: EMBEDDING_DIMENSIONS,
  provider: "cohere",
};
