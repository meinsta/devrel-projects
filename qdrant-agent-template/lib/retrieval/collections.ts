import { getQdrantClient } from "./client";
import { env } from "@/lib/shared/env";
import { logger } from "@/lib/shared/logger";

// Collection names
export const COLLECTIONS = {
  CORPUS_CHUNKS: "corpus_chunks",
  AGENT_TRACES: "agent_traces",
  AGENT_MEMORY: "agent_memory",
} as const;

/**
 * Create all required collections
 * Idempotent - skips if collections already exist
 */
export async function createCollections(): Promise<void> {
  const client = getQdrantClient();

  // Check existing collections
  const { collections } = await client.getCollections();
  const existingNames = new Set(collections.map((c) => c.name));

  // Corpus chunks collection (dense + sparse vectors)
  if (!existingNames.has(COLLECTIONS.CORPUS_CHUNKS)) {
    logger.info(`Creating collection: ${COLLECTIONS.CORPUS_CHUNKS}`);
    await client.createCollection(COLLECTIONS.CORPUS_CHUNKS, {
      vectors: {
        dense: {
          size: env.EMBED_SIZE,
          distance: "Cosine",
        },
      },
      sparse_vectors: {
        sparse: {},
      },
    });

    // Create payload indexes for filtering
    await Promise.all([
      client.createPayloadIndex(COLLECTIONS.CORPUS_CHUNKS, {
        field_name: "doc_id",
        field_schema: "keyword",
      }),
      client.createPayloadIndex(COLLECTIONS.CORPUS_CHUNKS, {
        field_name: "source",
        field_schema: "keyword",
      }),
      client.createPayloadIndex(COLLECTIONS.CORPUS_CHUNKS, {
        field_name: "access_scope",
        field_schema: "keyword",
      }),
      client.createPayloadIndex(COLLECTIONS.CORPUS_CHUNKS, {
        field_name: "tags",
        field_schema: "keyword",
      }),
      client.createPayloadIndex(COLLECTIONS.CORPUS_CHUNKS, {
        field_name: "created_at",
        field_schema: "datetime",
      }),
    ]);
    logger.info(`Created collection: ${COLLECTIONS.CORPUS_CHUNKS}`);
  }

  // Agent traces collection
  if (!existingNames.has(COLLECTIONS.AGENT_TRACES)) {
    logger.info(`Creating collection: ${COLLECTIONS.AGENT_TRACES}`);
    await client.createCollection(COLLECTIONS.AGENT_TRACES, {
      vectors: {
        dense: {
          size: env.EMBED_SIZE,
          distance: "Cosine",
        },
      },
    });

    await Promise.all([
      client.createPayloadIndex(COLLECTIONS.AGENT_TRACES, {
        field_name: "trace_id",
        field_schema: "keyword",
      }),
      client.createPayloadIndex(COLLECTIONS.AGENT_TRACES, {
        field_name: "user_id",
        field_schema: "keyword",
      }),
      client.createPayloadIndex(COLLECTIONS.AGENT_TRACES, {
        field_name: "status",
        field_schema: "keyword",
      }),
      client.createPayloadIndex(COLLECTIONS.AGENT_TRACES, {
        field_name: "created_at",
        field_schema: "datetime",
      }),
    ]);
    logger.info(`Created collection: ${COLLECTIONS.AGENT_TRACES}`);
  }

  // Agent memory collection
  if (!existingNames.has(COLLECTIONS.AGENT_MEMORY)) {
    logger.info(`Creating collection: ${COLLECTIONS.AGENT_MEMORY}`);
    await client.createCollection(COLLECTIONS.AGENT_MEMORY, {
      vectors: {
        dense: {
          size: env.EMBED_SIZE,
          distance: "Cosine",
        },
      },
    });

    await Promise.all([
      client.createPayloadIndex(COLLECTIONS.AGENT_MEMORY, {
        field_name: "user_id",
        field_schema: "keyword",
      }),
      client.createPayloadIndex(COLLECTIONS.AGENT_MEMORY, {
        field_name: "type",
        field_schema: "keyword",
      }),
      client.createPayloadIndex(COLLECTIONS.AGENT_MEMORY, {
        field_name: "created_at",
        field_schema: "datetime",
      }),
    ]);
    logger.info(`Created collection: ${COLLECTIONS.AGENT_MEMORY}`);
  }

  logger.info("All collections ready");
}

/**
 * Delete all collections (for testing/reset)
 */
export async function deleteAllCollections(): Promise<void> {
  const client = getQdrantClient();

  for (const name of Object.values(COLLECTIONS)) {
    try {
      await client.deleteCollection(name);
      logger.info(`Deleted collection: ${name}`);
    } catch {
      // Collection doesn't exist, ignore
    }
  }
}

/**
 * Get collection info
 */
export async function getCollectionInfo(name: string) {
  const client = getQdrantClient();
  return client.getCollection(name);
}
