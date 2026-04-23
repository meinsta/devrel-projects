/**
 * Memory types for agent personalization
 */

/**
 * Type of memory
 */
export type MemoryType = "episodic" | "preference" | "fact";

/**
 * Memory record
 */
export interface Memory {
  id: string;
  userId: string;
  type: MemoryType;
  content: string;
  metadata: {
    traceId?: string;
    confidence: number;
    source?: string;
    tags?: string[];
  };
  createdAt: string;
  lastAccessedAt: string;
  accessCount: number;
}

/**
 * Memory creation input
 */
export interface CreateMemoryInput {
  userId: string;
  type: MemoryType;
  content: string;
  metadata?: {
    traceId?: string;
    confidence?: number;
    source?: string;
    tags?: string[];
  };
}

/**
 * Memory query options
 */
export interface MemoryQueryOptions {
  userId: string;
  types?: MemoryType[];
  limit?: number;
  minConfidence?: number;
}

/**
 * Extracted memory from interaction
 */
export interface ExtractedMemory {
  type: MemoryType;
  content: string;
  confidence: number;
}
