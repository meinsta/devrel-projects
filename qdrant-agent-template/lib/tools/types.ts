import { z } from "zod";

/**
 * Base tool definition
 */
export interface ToolDefinition<TInput = unknown, TOutput = unknown> {
  name: string;
  description: string;
  category: ToolCategory;
  inputSchema: z.ZodType<TInput, z.ZodTypeDef, unknown>;
  outputSchema: z.ZodType<TOutput, z.ZodTypeDef, unknown>;
  execute: (input: TInput) => Promise<TOutput>;
}

/**
 * Tool categories for routing
 */
export type ToolCategory =
  | "knowledge"      // Qdrant vector search
  | "web"            // Internet search (Linkup)
  | "compute"        // Code execution, calculations
  | "multimodal"     // Image/video/audio analysis
  | "memory"         // User memory operations
  | "action";        // External actions (APIs, etc.)

/**
 * Tool call request from LLM
 */
export interface ToolCall {
  id: string;
  name: string;
  input: unknown;
}

/**
 * Tool execution result
 */
export interface ToolResult {
  callId: string;
  name: string;
  success: boolean;
  output?: unknown;
  error?: string;
  latencyMs: number;
}

/**
 * Tool routing decision
 */
export interface ToolRoutingDecision {
  shouldUseTool: boolean;
  selectedTools: ToolSelection[];
  reasoning: string;
  confidence: number;
}

export interface ToolSelection {
  name: string;
  priority: number;
  input: unknown;
  reasoning: string;
}

// ============================================
// Tool-specific schemas
// ============================================

/**
 * Linkup Web Search
 */
export const LinkupSearchInputSchema = z.object({
  query: z.string().describe("Search query for the web"),
  depth: z.enum(["basic", "standard", "deep"]).optional().default("standard"),
  outputType: z.enum(["searchResults", "sourcedAnswer", "structured"]).optional().default("searchResults"),
});
export type LinkupSearchInput = z.output<typeof LinkupSearchInputSchema>;

export const LinkupSearchResultSchema = z.object({
  results: z.array(z.object({
    title: z.string(),
    url: z.string(),
    snippet: z.string(),
    content: z.string().optional(),
  })),
  answer: z.string().optional(),
});
export type LinkupSearchResult = z.infer<typeof LinkupSearchResultSchema>;

/**
 * Qdrant Knowledge Search (existing retrieval)
 */
export const QdrantSearchInputSchema = z.object({
  query: z.string(),
  mode: z.enum(["dense", "sparse", "hybrid"]).optional().default("hybrid"),
  topK: z.number().optional().default(20),
  filters: z.object({
    source: z.string().optional(),
    tags: z.array(z.string()).optional(),
    docId: z.string().optional(),
  }).optional(),
});
export type QdrantSearchInput = z.output<typeof QdrantSearchInputSchema>;

export const QdrantSearchResultSchema = z.object({
  chunks: z.array(z.object({
    id: z.string(),
    text: z.string(),
    score: z.number(),
    metadata: z.record(z.unknown()),
  })),
  totalFound: z.number(),
});
export type QdrantSearchResult = z.infer<typeof QdrantSearchResultSchema>;

/**
 * Image Analysis (multimodal)
 */
export const ImageAnalysisInputSchema = z.object({
  imageUrl: z.string().url().optional(),
  imageBase64: z.string().optional(),
  prompt: z.string().describe("What to analyze in the image"),
  extractText: z.boolean().optional().default(false),
});
export type ImageAnalysisInput = z.output<typeof ImageAnalysisInputSchema>;

export const ImageAnalysisResultSchema = z.object({
  description: z.string(),
  extractedText: z.string().optional(),
  objects: z.array(z.string()).optional(),
  embedding: z.array(z.number()).optional(),
});
export type ImageAnalysisResult = z.infer<typeof ImageAnalysisResultSchema>;

/**
 * Code Execution
 */
export const CodeExecutionInputSchema = z.object({
  language: z.enum(["python", "javascript", "typescript"]),
  code: z.string(),
  timeout: z.number().default(30000),
});
export type CodeExecutionInput = z.infer<typeof CodeExecutionInputSchema>;

export const CodeExecutionResultSchema = z.object({
  stdout: z.string(),
  stderr: z.string(),
  exitCode: z.number(),
  executionTimeMs: z.number(),
});
export type CodeExecutionResult = z.infer<typeof CodeExecutionResultSchema>;

/**
 * Memory Operations
 */
export const MemorySearchInputSchema = z.object({
  userId: z.string(),
  query: z.string(),
  types: z.array(z.enum(["episodic", "preference", "fact"])).optional(),
  limit: z.number().default(10),
});
export type MemorySearchInput = z.infer<typeof MemorySearchInputSchema>;

export const MemorySearchResultSchema = z.object({
  memories: z.array(z.object({
    id: z.string(),
    type: z.string(),
    content: z.string(),
    createdAt: z.string(),
    relevance: z.number(),
  })),
});
export type MemorySearchResult = z.infer<typeof MemorySearchResultSchema>;

/**
 * All available tools enum
 */
export const ToolName = {
  LINKUP_SEARCH: "linkup_search",
  QDRANT_SEARCH: "qdrant_search",
  IMAGE_ANALYSIS: "image_analysis",
  CODE_EXECUTION: "code_execution",
  MEMORY_SEARCH: "memory_search",
} as const;

export type ToolNameType = typeof ToolName[keyof typeof ToolName];
