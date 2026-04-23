import { logger } from "@/lib/shared/logger";
import { generateId } from "@/lib/shared/ids";
import { toolRegistry } from "./registry";
import type { ToolSelection, ToolResult, ToolCall } from "./types";

/**
 * Execute a single tool call
 */
async function executeToolCall(call: ToolCall): Promise<ToolResult> {
  const startTime = Date.now();
  const log = logger.child({ toolName: call.name, callId: call.id });

  log.debug("Executing tool call", { input: call.input });

  try {
    const tool = toolRegistry.get(call.name);
    if (!tool) {
      throw new Error(`Tool not found: ${call.name}`);
    }

    // Validate input
    const validatedInput = tool.inputSchema.parse(call.input);

    // Execute the tool
    const output = await tool.execute(validatedInput);

    const latencyMs = Date.now() - startTime;
    log.info("Tool execution succeeded", { latencyMs });

    return {
      callId: call.id,
      name: call.name,
      success: true,
      output,
      latencyMs,
    };
  } catch (error) {
    const latencyMs = Date.now() - startTime;
    const errorMessage = (error as Error).message;

    log.error("Tool execution failed", error as Error);

    return {
      callId: call.id,
      name: call.name,
      success: false,
      error: errorMessage,
      latencyMs,
    };
  }
}

/**
 * Execute multiple tools in parallel
 * Sorted by priority, but all run concurrently
 */
export async function executeTools(
  selections: ToolSelection[]
): Promise<ToolResult[]> {
  const log = logger.child({ component: "tool-executor" });

  if (selections.length === 0) {
    return [];
  }

  // Sort by priority (highest first) for logging, but execute all in parallel
  const sortedSelections = [...selections].sort((a, b) => b.priority - a.priority);

  log.info("Executing tools", {
    tools: sortedSelections.map((s) => s.name),
    count: sortedSelections.length,
  });

  // Convert selections to tool calls
  const calls: ToolCall[] = sortedSelections.map((s) => ({
    id: generateId(),
    name: s.name,
    input: s.input,
  }));

  // Execute all tools in parallel
  const startTime = Date.now();
  const results = await Promise.all(calls.map(executeToolCall));

  log.info("All tools executed", {
    totalLatencyMs: Date.now() - startTime,
    successCount: results.filter((r) => r.success).length,
    failureCount: results.filter((r) => !r.success).length,
  });

  return results;
}

/**
 * Execute tools sequentially (for dependent operations)
 */
export async function executeToolsSequential(
  selections: ToolSelection[]
): Promise<ToolResult[]> {
  const log = logger.child({ component: "tool-executor" });

  if (selections.length === 0) {
    return [];
  }

  // Sort by priority (highest first)
  const sortedSelections = [...selections].sort((a, b) => b.priority - a.priority);

  log.info("Executing tools sequentially", {
    tools: sortedSelections.map((s) => s.name),
  });

  const results: ToolResult[] = [];

  for (const selection of sortedSelections) {
    const call: ToolCall = {
      id: generateId(),
      name: selection.name,
      input: selection.input,
    };

    const result = await executeToolCall(call);
    results.push(result);

    // Stop on failure if needed (optional behavior)
    if (!result.success) {
      log.warn("Tool failed, continuing with remaining tools", {
        failedTool: selection.name,
      });
    }
  }

  return results;
}

/**
 * Format tool results for LLM consumption
 */
export function formatToolResultsForLLM(results: ToolResult[]): string {
  if (results.length === 0) {
    return "No tool results available.";
  }

  const sections: string[] = [];

  for (const result of results) {
    if (result.success) {
      sections.push(`## ${result.name} (${result.latencyMs}ms)
${JSON.stringify(result.output, null, 2)}`);
    } else {
      sections.push(`## ${result.name} (FAILED)
Error: ${result.error}`);
    }
  }

  return sections.join("\n\n---\n\n");
}

/**
 * Merge tool results with existing evidence
 * Useful for combining web search with vector search
 */
export function mergeToolResults(
  vectorResults: unknown[],
  toolResults: ToolResult[]
): {
  combined: unknown[];
  sources: { type: string; count: number }[];
} {
  const combined: unknown[] = [...vectorResults];
  const sources: { type: string; count: number }[] = [
    { type: "knowledge_base", count: vectorResults.length },
  ];

  for (const result of toolResults) {
    if (!result.success) continue;

    if (result.name === "linkup_search") {
      const webOutput = result.output as { results?: Array<Record<string, unknown>> };
      if (webOutput.results) {
        combined.push(
          ...webOutput.results.map((r) => ({
            ...r,
            _source: "web",
          }))
        );
        sources.push({ type: "web_search", count: webOutput.results.length });
      }
    } else if (result.name === "image_analysis") {
      combined.push({
        type: "image_analysis",
        content: result.output,
        _source: "multimodal",
      });
      sources.push({ type: "image_analysis", count: 1 });
    }
  }

  return { combined, sources };
}

/**
 * Check if any tool results contain errors
 */
export function hasToolErrors(results: ToolResult[]): boolean {
  return results.some((r) => !r.success);
}

/**
 * Get successful tool outputs by name
 */
export function getToolOutput<T>(
  results: ToolResult[],
  toolName: string
): T | undefined {
  const result = results.find((r) => r.name === toolName && r.success);
  return result?.output as T | undefined;
}
