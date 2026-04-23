import { z } from "zod";
import { generateJSON } from "@/lib/llm/client";
import { PLANNER_SYSTEM, PLANNER_USER } from "@/lib/llm/prompts";
import { logger } from "@/lib/shared/logger";
import type { SubQuery, RouteDecision, QueryBundle, RetrievalBudget } from "./types";

const QueryPlanSchema = z.object({
  queries: z.array(z.object({
    text: z.string(),
    intent: z.string(),
    weight: z.number().min(0).max(1),
  })).min(3).max(8),
  mustHaveEntities: z.array(z.string()).optional(),
  lexicalTerms: z.array(z.string()).optional(),
});

/**
 * Generate sub-queries for multi-query retrieval
 */
export async function planQueries(
  query: string,
  route: RouteDecision
): Promise<SubQuery[]> {
  logger.debug("Planning queries", { originalQuery: query });

  const routeContext = `Mode: ${route.mode}, Budget: ${route.budget.maxChunks} chunks`;

  const result = await generateJSON({
    tier: "cheap",
    system: PLANNER_SYSTEM,
    prompt: PLANNER_USER(query, routeContext),
    schema: QueryPlanSchema,
  });

  // Normalize weights to sum to 1
  const totalWeight = result.queries.reduce((sum, q) => sum + q.weight, 0);
  const normalizedQueries = result.queries.map((q) => ({
    ...q,
    weight: q.weight / totalWeight,
  }));

  logger.debug("Generated sub-queries", { count: normalizedQueries.length });

  return normalizedQueries;
}

/**
 * Simple query expansion (fallback, no LLM call)
 */
export function planQueriesSimple(query: string): SubQuery[] {
  const queries: SubQuery[] = [];

  // Original query
  queries.push({
    text: query,
    intent: "original",
    weight: 0.4,
  });

  // Extract key terms and create variations
  const words = query.toLowerCase().split(/\s+/).filter((w) => w.length > 3);
  const keyTerms = words.slice(0, 5);

  if (keyTerms.length >= 2) {
    // Key terms focused query
    queries.push({
      text: keyTerms.join(" "),
      intent: "key_terms",
      weight: 0.2,
    });
  }

  // Question to statement conversion
  if (/^(what|how|why|when|where|who|which)/i.test(query)) {
    const statement = query
      .replace(/^what (is|are) /i, "")
      .replace(/^how (do|does|to) /i, "")
      .replace(/^why (is|are|do|does) /i, "")
      .replace(/\?$/, "");
    
    if (statement !== query) {
      queries.push({
        text: statement,
        intent: "statement",
        weight: 0.2,
      });
    }
  }

  // Broader context query
  queries.push({
    text: `${query} overview explanation`,
    intent: "context",
    weight: 0.2,
  });

  // Normalize weights
  const totalWeight = queries.reduce((sum, q) => sum + q.weight, 0);
  return queries.map((q) => ({
    ...q,
    weight: q.weight / totalWeight,
  }));
}

/**
 * Create a query bundle from planning results
 */
export function createQueryBundle(
  originalQuery: string,
  queries: SubQuery[],
  route: RouteDecision
): QueryBundle {
  return {
    originalQuery,
    queries,
    filters: route.filters,
    budget: route.budget,
  };
}

/**
 * Rewrite queries based on critique feedback
 */
export async function rewriteQueries(
  originalQuery: string,
  missingIntents: string[],
  existingQueries: SubQuery[]
): Promise<SubQuery[]> {
  logger.debug("Rewriting queries", { missingIntents });

  const rewritePrompt = `
Original query: "${originalQuery}"

Current sub-queries that didn't fully cover the question:
${existingQueries.map((q) => `- ${q.text} (intent: ${q.intent})`).join("\n")}

Missing aspects that need to be addressed:
${missingIntents.map((i) => `- ${i}`).join("\n")}

Generate new sub-queries that specifically address the missing aspects while keeping some of the working queries.
`;

  const result = await generateJSON({
    tier: "cheap",
    system: PLANNER_SYSTEM,
    prompt: rewritePrompt,
    schema: QueryPlanSchema,
  });

  // Normalize weights
  const totalWeight = result.queries.reduce((sum, q) => sum + q.weight, 0);
  return result.queries.map((q) => ({
    ...q,
    weight: q.weight / totalWeight,
  }));
}
