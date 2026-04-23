import { getQdrantClient } from "@/lib/retrieval/client";
import { COLLECTIONS } from "@/lib/retrieval/collections";
import { embedder } from "@/lib/retrieval/embedder";
import { generateDocId, generateChunkId, hashText } from "@/lib/shared/ids";
import { logger } from "@/lib/shared/logger";
import { chunkText, chunkCode } from "./chunker";
import { parseDocument } from "./parser";
import type { ChunkPayload } from "@/lib/retrieval/types";

/**
 * Document input for ingestion
 */
export interface DocumentInput {
  id?: string;
  content: string;
  metadata: {
    source: string;
    title?: string;
    url?: string;
    filename?: string;
    format?: string;
    accessScope?: string;
    tags?: string[];
    path?: string;
    lang?: string;
  };
}

/**
 * Ingestion result
 */
export interface IngestionResult {
  docId: string;
  chunkIds: string[];
  chunkCount: number;
  totalTokens: number;
  status: "success" | "error";
  error?: string;
}

/**
 * Ingestion options
 */
export interface IngestionOptions {
  maxTokensPerChunk?: number;
  overlapTokens?: number;
  skipDuplicates?: boolean;
}

const DEFAULT_OPTIONS: IngestionOptions = {
  maxTokensPerChunk: 500,
  overlapTokens: 50,
  skipDuplicates: false, // Disabled by default now
};

/**
 * Ingest a single document
 */
export async function ingestDocument(
  doc: DocumentInput,
  options: IngestionOptions = {}
): Promise<IngestionResult> {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const docId = doc.id || generateDocId();

  logger.debug("Ingesting document", { docId, source: doc.metadata.source });

  try {
    // Parse document
    const parsed = parseDocument(doc.content, {
      filename: doc.metadata.filename,
      format: doc.metadata.format,
    });

    // Determine title
    const title = doc.metadata.title || parsed.title || doc.metadata.filename || "Untitled";

    // Chunk document
    const isCode = parsed.metadata.format === "code";
    const chunks = isCode
      ? chunkCode(parsed.content, parsed.metadata.language || "text", {
          maxTokens: opts.maxTokensPerChunk,
          overlapTokens: opts.overlapTokens,
        })
      : chunkText(parsed.content, {
          maxTokens: opts.maxTokensPerChunk,
          overlapTokens: opts.overlapTokens,
        });

    if (chunks.length === 0) {
      return {
        docId,
        chunkIds: [],
        chunkCount: 0,
        totalTokens: 0,
        status: "success",
      };
    }

    // Generate embeddings for all chunks
    const chunkTexts = chunks.map((c) => c.text);
    const embeddings = await embedder.embedDocuments(chunkTexts);

    // Build points for Qdrant
    const now = new Date().toISOString();
    const points = chunks.map((chunk, index) => {
      const chunkId = generateChunkId();
      const hash = hashText(chunk.text);

      const payload: ChunkPayload = {
        doc_id: docId,
        chunk_id: chunkId,
        text: chunk.text,
        source: doc.metadata.source,
        title: `${title} (${index + 1}/${chunks.length})`,
        url: doc.metadata.url,
        created_at: now,
        access_scope: doc.metadata.accessScope || "public",
        tags: doc.metadata.tags || [],
        path: doc.metadata.path,
        lang: doc.metadata.lang || parsed.metadata.language,
        section: parsed.metadata.sections?.[0],
        token_count: chunk.tokenCount,
        hash,
      };

      // Get sparse vector
      const sparse = embedder.getSparseVector(chunk.text);

      return {
        id: chunkId,
        payload: payload as unknown as Record<string, unknown>,
        vector: {
          dense: embeddings[index],
          sparse: sparse,
        },
      };
    });

    // Upsert points
    const client = getQdrantClient();
    await client.upsert(COLLECTIONS.CORPUS_CHUNKS, { points });

    const totalTokens = chunks.reduce((sum, c) => sum + c.tokenCount, 0);

    logger.info("Document ingested", {
      docId,
      chunks: points.length,
      tokens: totalTokens,
    });

    return {
      docId,
      chunkIds: points.map((p) => p.id as string),
      chunkCount: points.length,
      totalTokens,
      status: "success",
    };
  } catch (error) {
    logger.error("Ingestion failed", error as Error, { docId });
    return {
      docId,
      chunkIds: [],
      chunkCount: 0,
      totalTokens: 0,
      status: "error",
      error: (error as Error).message,
    };
  }
}

/**
 * Ingest multiple documents
 */
export async function ingestDocuments(
  docs: DocumentInput[],
  options: IngestionOptions = {}
): Promise<IngestionResult[]> {
  const results: IngestionResult[] = [];

  // Process sequentially to avoid rate limits
  for (const doc of docs) {
    const result = await ingestDocument(doc, options);
    results.push(result);
  }

  return results;
}

/**
 * Delete a document and all its chunks
 */
export async function deleteDocument(docId: string): Promise<number> {
  const client = getQdrantClient();

  // Find all chunks for this document
  const results = await client.scroll(COLLECTIONS.CORPUS_CHUNKS, {
    filter: {
      must: [{ key: "doc_id", match: { value: docId } }],
    },
    limit: 10000,
  });

  if (results.points.length === 0) {
    return 0;
  }

  // Delete chunks
  await client.delete(COLLECTIONS.CORPUS_CHUNKS, {
    points: results.points.map((p) => p.id),
  });

  logger.info("Document deleted", { docId, chunks: results.points.length });
  return results.points.length;
}

/**
 * Get document info
 */
export async function getDocumentInfo(docId: string): Promise<{
  docId: string;
  chunkCount: number;
  totalTokens: number;
  metadata?: Record<string, unknown>;
} | null> {
  const client = getQdrantClient();

  const results = await client.scroll(COLLECTIONS.CORPUS_CHUNKS, {
    filter: {
      must: [{ key: "doc_id", match: { value: docId } }],
    },
    limit: 1000,
    with_payload: true,
  });

  if (results.points.length === 0) {
    return null;
  }

  const chunks = results.points.map((p) => p.payload as unknown as ChunkPayload);
  const totalTokens = chunks.reduce((sum, c) => sum + c.token_count, 0);

  return {
    docId,
    chunkCount: chunks.length,
    totalTokens,
    metadata: {
      source: chunks[0].source,
      title: chunks[0].title,
      url: chunks[0].url,
      created_at: chunks[0].created_at,
      tags: chunks[0].tags,
    },
  };
}

/**
 * List all documents
 */
export async function listDocuments(options: {
  source?: string;
  limit?: number;
} = {}): Promise<Array<{ docId: string; title: string; source: string; chunkCount: number }>> {
  const client = getQdrantClient();
  const { source, limit = 100 } = options;

  const filter = source
    ? { must: [{ key: "source", match: { value: source } }] }
    : undefined;

  const results = await client.scroll(COLLECTIONS.CORPUS_CHUNKS, {
    filter,
    limit: 10000,
    with_payload: { include: ["doc_id", "title", "source"] },
  });

  // Group by doc_id
  const docs = new Map<string, { title: string; source: string; count: number }>();

  for (const point of results.points) {
    const payload = point.payload as { doc_id: string; title: string; source: string };
    const existing = docs.get(payload.doc_id);
    if (existing) {
      existing.count++;
    } else {
      docs.set(payload.doc_id, {
        title: payload.title.replace(/\s+\(\d+\/\d+\)$/, ""), // Remove chunk suffix
        source: payload.source,
        count: 1,
      });
    }
  }

  return Array.from(docs.entries())
    .slice(0, limit)
    .map(([docId, info]) => ({
      docId,
      title: info.title,
      source: info.source,
      chunkCount: info.count,
    }));
}
