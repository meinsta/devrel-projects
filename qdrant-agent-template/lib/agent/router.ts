import { z } from "zod";
import { generateJSON } from "@/lib/llm/client";
import { ROUTER_SYSTEM, ROUTER_USER } from "@/lib/llm/prompts";
import { logger } from "@/lib/shared/logger";
import type { RouteDecision, UserContext } from "./types";

const RouteDecisionSchema = z.object({
  mode: z.enum(["dense", "sparse", "hybrid"]),
  corpora: z.array(z.string()).optional(),
  filters: z.object({
    source: z.array(z.string()).optional(),
    tags: z.array(z.string()).optional(),
    timeRange: z.object({
      start: z.string().optional(),
      end: z.string().optional(),
    }).optional(),
    accessScope: z.string().optional(),
  }).optional(),
  budget: z.object({
    latencyMs: z.number().optional(),
    maxChunks: z.number().optional(),
    maxTokensContext: z.number().optional(),
  }).optional(),
  reasoning: z.string(),
});

/**
 * Route a query to determine retrieval strategy
 */
export async function routeQuery(
  query: string,
  userContext?: UserContext
): Promise<RouteDecision> {
  logger.debug("Routing query", { queryLength: query.length });

  const userContextSummary = userContext?.memories?.length
    ? `User preferences: ${userContext.memories.slice(0, 3).join("; ")}`
    : undefined;

  const result = await generateJSON({
    tier: "cheap",
    system: ROUTER_SYSTEM,
    prompt: ROUTER_USER(query, userContextSummary),
    schema: RouteDecisionSchema,
  });

  logger.debug("Route decision", { mode: result.mode, reasoning: result.reasoning });

  // Apply defaults
  return {
    mode: result.mode,
    corpora: result.corpora || ["corpus_chunks"],
    filters: result.filters || {},
    budget: {
      latencyMs: result.budget?.latencyMs || 3000,
      maxChunks: result.budget?.maxChunks || 30,
      maxTokensContext: result.budget?.maxTokensContext || 4500,
    },
    reasoning: result.reasoning,
  };
}

/**
 * Simple heuristic router (fallback, no LLM call)
 */
export function routeQuerySimple(query: string): RouteDecision {
  // Check for code-like patterns
  const hasCodePatterns = /[`{}()\[\];=<>]|function|class|const|let|var|import|export/.test(query);
  
  // Check for error codes or exact phrases
  const hasExactTerms = /error|exception|code|"[^"]+"|'[^']+'|\b[A-Z]{2,}_[A-Z_]+\b/.test(query);
  
  // Check for natural language question patterns
  const isNaturalQuestion = /^(what|how|why|when|where|who|which|can|could|should|would|is|are|do|does)/i.test(query);

  let mode: "dense" | "sparse" | "hybrid";
  let reasoning: string;

  if (hasCodePatterns || hasExactTerms) {
    mode = "hybrid";
    reasoning = "Query contains code patterns or exact terms - using hybrid search";
  } else if (isNaturalQuestion) {
    mode = "dense";
    reasoning = "Natural language question - using semantic search";
  } else {
    mode = "hybrid";
    reasoning = "Default to hybrid for balanced retrieval";
  }

  return {
    mode,
    corpora: ["corpus_chunks"],
    filters: {},
    budget: {
      latencyMs: 3000,
      maxChunks: 30,
      maxTokensContext: 4500,
    },
    reasoning,
  };
}
