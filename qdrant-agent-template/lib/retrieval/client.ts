import { QdrantClient } from "@qdrant/js-client-rest";
import { env } from "@/lib/shared/env";

let client: QdrantClient | null = null;

/**
 * Get singleton Qdrant client instance
 */
export function getQdrantClient(): QdrantClient {
  if (!client) {
    client = new QdrantClient({
      url: env.QDRANT_URL,
      apiKey: env.QDRANT_API_KEY,
    });
  }
  return client;
}

/**
 * Check if Qdrant is healthy
 */
export async function checkQdrantHealth(): Promise<boolean> {
  try {
    const qdrant = getQdrantClient();
    await qdrant.getCollections();
    return true;
  } catch {
    return false;
  }
}
