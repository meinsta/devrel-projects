import { z } from "zod";
import { generateJSON } from "@/lib/llm/client";
import { CORRECTIVE_SYSTEM, CORRECTIVE_USER } from "@/lib/llm/prompts";
import { logger } from "@/lib/shared/logger";
import { rewriteQueries } from "./planner";
import type { AgentContext, CorrectiveAction, SubQuery } from "./types";
import type { RetrievalMode } from "@/lib/retrieval/types";

const CorrectiveActionSchema = z.object({
  action: z.enum(["NONE", "REWRITE_QUERIES", "SWITCH_MODE", "BROADEN_SCOPE", "INCREASE_DEPTH"]),
  reasoning: z.string(),
  newMode: z.enum(["dense", "sparse", "hybrid"]).optional(),
  newTopK: z.number().optional(),
});

/**
 * Decide on corrective action based on critique
 */
export async function decideCorrectiveAction(
  ctx: AgentContext
): Promise<CorrectiveAction> {
  const { critique, loopCount, route, query, queryBundle } = ctx;

  if (!critique || !route) {
    return { type: "NONE" };
  }

  logger.debug("Deciding corrective action", {
    confidence: critique.overallConfidence,
    loopCount,
  });

  // Use LLM to decide
  const result = await generateJSON({
    tier: "cheap",
    system: CORRECTIVE_SYSTEM,
    prompt: CORRECTIVE_USER(query, critique, route.mode, loopCount),
    schema: CorrectiveActionSchema,
  });

  logger.debug("Corrective decision", { action: result.action, reasoning: result.reasoning });

  // Build the action
  switch (result.action) {
    case "REWRITE_QUERIES":
      if (queryBundle) {
        const newQueries = await rewriteQueries(
          query,
          critique.missingIntents,
          queryBundle.queries
        );
        return { type: "REWRITE_QUERIES", newQueries };
      }
      return { type: "NONE" };

    case "SWITCH_MODE":
      const newMode = result.newMode || getAlternativeMode(route.mode);
      return { type: "SWITCH_MODE", newMode };

    case "BROADEN_SCOPE":
      const filterKeys = Object.keys(route.filters);
      return { type: "BROADEN_SCOPE", removedFilters: filterKeys };

    case "INCREASE_DEPTH":
      const newTopK = result.newTopK || route.budget.maxChunks * 2;
      return { type: "INCREASE_DEPTH", newTopK };

    default:
      return { type: "NONE" };
  }
}

/**
 * Simple corrective action selection (no LLM)
 */
export function decideCorrectiveActionSimple(
  ctx: AgentContext
): CorrectiveAction {
  const { critique, loopCount, route, queryBundle } = ctx;

  if (!critique || !route) {
    return { type: "NONE" };
  }

  // First loop: try query rewrite if we have missing intents
  if (loopCount === 0 && critique.missingIntents.length > 0) {
    // Generate simple rewrites
    const newQueries: SubQuery[] = [
      ...(queryBundle?.queries.slice(0, 2) || []),
      ...critique.missingIntents.slice(0, 3).map((intent, i) => ({
        text: intent,
        intent: `missing_${i}`,
        weight: 0.3,
      })),
    ];
    
    // Normalize weights
    const total = newQueries.reduce((s, q) => s + q.weight, 0);
    const normalized = newQueries.map((q) => ({ ...q, weight: q.weight / total }));
    
    return { type: "REWRITE_QUERIES", newQueries: normalized };
  }

  // Second loop: try switching mode
  if (loopCount === 1) {
    const newMode = getAlternativeMode(route.mode);
    return { type: "SWITCH_MODE", newMode };
  }

  // Third loop: broaden scope if we have filters
  if (loopCount === 2 && Object.keys(route.filters).length > 0) {
    return { type: "BROADEN_SCOPE", removedFilters: Object.keys(route.filters) };
  }

  // Last resort: increase depth
  return { type: "INCREASE_DEPTH", newTopK: route.budget.maxChunks * 2 };
}

/**
 * Get an alternative retrieval mode
 */
function getAlternativeMode(current: RetrievalMode): RetrievalMode {
  switch (current) {
    case "dense":
      return "hybrid";
    case "sparse":
      return "hybrid";
    case "hybrid":
      return "sparse"; // Try more lexical if hybrid failed
    default:
      return "hybrid";
  }
}

/**
 * Apply corrective action to context
 */
export function applyCorrectiveAction(
  ctx: AgentContext,
  action: CorrectiveAction
): void {
  if (!ctx.route || !ctx.queryBundle) return;

  switch (action.type) {
    case "REWRITE_QUERIES":
      ctx.queryBundle.queries = action.newQueries;
      break;

    case "SWITCH_MODE":
      ctx.route.mode = action.newMode;
      break;

    case "BROADEN_SCOPE":
      ctx.queryBundle.filters = {};
      ctx.route.filters = {};
      break;

    case "INCREASE_DEPTH":
      ctx.queryBundle.budget.maxChunks = action.newTopK;
      ctx.route.budget.maxChunks = action.newTopK;
      break;
  }

  ctx.correctiveActions.push(action);
}
