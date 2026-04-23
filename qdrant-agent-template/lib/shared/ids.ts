import { ulid } from "ulid";
import { randomUUID } from "crypto";

/**
 * Generate a ULID (Universally Unique Lexicographically Sortable Identifier)
 * ULIDs are sortable by creation time and are URL-safe
 */
export function generateId(): string {
  return ulid();
}

/**
 * Generate a UUID v4 - required for Qdrant point IDs
 */
export function generateUUID(): string {
  return randomUUID();
}

/**
 * Generate a prefixed ID for better readability in logs
 * Note: Use generateUUID() for Qdrant point IDs
 */
export function generatePrefixedId(prefix: string): string {
  return `${prefix}_${ulid()}`;
}

/**
 * Generate a trace ID
 */
export function generateTraceId(): string {
  return generatePrefixedId("trc");
}

/**
 * Generate a chunk ID (UUID for Qdrant compatibility)
 */
export function generateChunkId(): string {
  return randomUUID();
}

/**
 * Generate a document ID
 */
export function generateDocId(): string {
  return generatePrefixedId("doc");
}

/**
 * Generate a memory ID (UUID for Qdrant compatibility)
 */
export function generateMemoryId(): string {
  return randomUUID();
}

/**
 * Simple hash function for deduplication
 */
export function hashText(text: string): string {
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    const char = text.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(36);
}
