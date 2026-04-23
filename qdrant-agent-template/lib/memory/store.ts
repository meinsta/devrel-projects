import { z } from "zod";
import { getQdrantClient } from "@/lib/retrieval/client";
import { COLLECTIONS } from "@/lib/retrieval/collections";
import { embedder } from "@/lib/retrieval/embedder";
import { generateMemoryId } from "@/lib/shared/ids";
import { logger } from "@/lib/shared/logger";
import { generateJSON } from "@/lib/llm/client";
import { MEMORY_SYSTEM, MEMORY_USER } from "@/lib/llm/prompts";
import type { Memory, CreateMemoryInput, MemoryQueryOptions, ExtractedMemory, MemoryType } from "./types";

const ExtractedMemoriesSchema = z.object({
  memories: z.array(z.object({
    type: z.enum(["episodic", "preference", "fact"]),
    content: z.string(),
    confidence: z.number().min(0).max(1),
  })),
});

/**
 * Create a new memory
 */
export async function createMemory(input: CreateMemoryInput): Promise<Memory> {
  const client = getQdrantClient();
  const id = generateMemoryId();
  const now = new Date().toISOString();

  const memory: Memory = {
    id,
    userId: input.userId,
    type: input.type,
    content: input.content,
    metadata: {
      confidence: input.metadata?.confidence ?? 0.8,
      traceId: input.metadata?.traceId,
      source: input.metadata?.source,
      tags: input.metadata?.tags,
    },
    createdAt: now,
    lastAccessedAt: now,
    accessCount: 0,
  };

  await client.upsert(COLLECTIONS.AGENT_MEMORY, {
    points: [
      {
        id,
        payload: memory as unknown as Record<string, unknown>,
        vector: {
          dense: embedder.getDenseQuery(input.content),
        },
      },
    ],
  });

  logger.info("Memory created", { id, type: input.type, userId: input.userId });
  return memory;
}

/**
 * Get memory by ID
 */
export async function getMemory(id: string): Promise<Memory | null> {
  const client = getQdrantClient();

  try {
    const results = await client.retrieve(COLLECTIONS.AGENT_MEMORY, {
      ids: [id],
      with_payload: true,
    });

    if (results.length === 0) return null;
    return results[0].payload as unknown as Memory;
  } catch {
    return null;
  }
}

/**
 * Search memories by semantic similarity
 */
export async function searchMemories(
  query: string,
  options: MemoryQueryOptions
): Promise<Memory[]> {
  const client = getQdrantClient();
  const { userId, types, limit = 10, minConfidence = 0 } = options;

  const must: unknown[] = [{ key: "userId", match: { value: userId } }];

  if (types && types.length > 0) {
    must.push({ key: "type", match: { any: types } });
  }

  if (minConfidence > 0) {
    must.push({ key: "metadata.confidence", range: { gte: minConfidence } });
  }

  const results = await client.query(COLLECTIONS.AGENT_MEMORY, {
    query: embedder.getDenseQuery(query),
    using: "dense",
    limit,
    filter: { must },
    with_payload: true,
  });

  const memories = (results.points || []).map((p) => p.payload as unknown as Memory);

  // Update access tracking
  await updateAccessTracking(memories.map((m) => m.id));

  return memories;
}

/**
 * List memories for a user
 */
export async function listMemories(
  userId: string,
  options: { types?: MemoryType[]; limit?: number } = {}
): Promise<Memory[]> {
  const client = getQdrantClient();
  const { types, limit = 50 } = options;

  const must: unknown[] = [{ key: "userId", match: { value: userId } }];

  if (types && types.length > 0) {
    must.push({ key: "type", match: { any: types } });
  }

  const results = await client.scroll(COLLECTIONS.AGENT_MEMORY, {
    filter: { must },
    limit,
    with_payload: true,
  });

  return results.points.map((p) => p.payload as unknown as Memory);
}

/**
 * Delete a memory
 */
export async function deleteMemory(id: string): Promise<boolean> {
  const client = getQdrantClient();

  try {
    await client.delete(COLLECTIONS.AGENT_MEMORY, {
      points: [id],
    });
    logger.info("Memory deleted", { id });
    return true;
  } catch {
    return false;
  }
}

/**
 * Delete all memories for a user
 */
export async function deleteUserMemories(userId: string): Promise<number> {
  const client = getQdrantClient();

  const results = await client.scroll(COLLECTIONS.AGENT_MEMORY, {
    filter: {
      must: [{ key: "userId", match: { value: userId } }],
    },
    limit: 1000,
  });

  if (results.points.length === 0) return 0;

  await client.delete(COLLECTIONS.AGENT_MEMORY, {
    points: results.points.map((p) => p.id),
  });

  logger.info("User memories deleted", { userId, count: results.points.length });
  return results.points.length;
}

/**
 * Update access tracking for memories
 */
async function updateAccessTracking(ids: string[]): Promise<void> {
  if (ids.length === 0) return;

  const client = getQdrantClient();
  const now = new Date().toISOString();

  // Note: Qdrant doesn't support increment operations, so we'd need to read-modify-write
  // For MVP, we'll just update lastAccessedAt
  for (const id of ids) {
    try {
      await client.setPayload(COLLECTIONS.AGENT_MEMORY, {
        points: [id],
        payload: {
          lastAccessedAt: now,
        },
      });
    } catch {
      // Ignore errors for access tracking
    }
  }
}

/**
 * Extract memories from a successful interaction
 */
export async function extractMemories(
  query: string,
  answer: string,
  wasHelpful: boolean
): Promise<ExtractedMemory[]> {
  if (!wasHelpful) {
    return [];
  }

  try {
    const result = await generateJSON({
      tier: "cheap",
      system: MEMORY_SYSTEM,
      prompt: MEMORY_USER(query, answer, wasHelpful),
      schema: ExtractedMemoriesSchema,
    });

    return result.memories;
  } catch (error) {
    logger.warn("Memory extraction failed", { error: (error as Error).message });
    return [];
  }
}

/**
 * Write memories from an interaction (if appropriate)
 */
export async function writeMemoriesFromInteraction(
  userId: string,
  traceId: string,
  query: string,
  answer: string,
  confidence: number
): Promise<number> {
  // Only write memories for high-confidence interactions
  if (confidence < 0.72) {
    return 0;
  }

  const extracted = await extractMemories(query, answer, true);
  let written = 0;

  for (const mem of extracted) {
    if (mem.confidence >= 0.6) {
      await createMemory({
        userId,
        type: mem.type,
        content: mem.content,
        metadata: {
          traceId,
          confidence: mem.confidence,
          source: "auto_extract",
        },
      });
      written++;
    }
  }

  logger.info("Memories written from interaction", { userId, traceId, written });
  return written;
}

/**
 * Get user context for agent (memories + preferences)
 */
export async function getUserContext(
  userId: string,
  query: string
): Promise<string[]> {
  // Get relevant memories
  const memories = await searchMemories(query, {
    userId,
    limit: 10,
    minConfidence: 0.5,
  });

  // Format as context strings
  return memories.map((m) => {
    const prefix = m.type === "preference" ? "User prefers:" : m.type === "fact" ? "Known:" : "Previous:";
    return `${prefix} ${m.content}`;
  });
}
