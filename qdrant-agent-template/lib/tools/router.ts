import { generateJSON } from "@/lib/llm/client";
import { logger } from "@/lib/shared/logger";
import { toolRegistry, ToolSelectionSchema, type ToolSelectionResult } from "./registry";
import { ToolName, type ToolRoutingDecision, type ToolSelection } from "./types";

/**
 * System prompt for tool routing
 */
const TOOL_ROUTER_SYSTEM = `You are an expert tool selector for an AI agent. Your job is to analyze user queries and decide which tools should be used to answer them effectively.

Available tools:
${toolRegistry.getToolDescriptions()}

Tool Selection Guidelines:
1. **qdrant_search** - Use for questions about documents, knowledge base content, historical information, or when the user asks about their data
2. **linkup_search** - Use for real-time information, current events, news, live data, or when knowledge base might be outdated
3. **image_analysis** - Use when the query involves an image URL, base64 image, or asks about visual content

Decision Rules:
- You can select MULTIPLE tools if the query requires different types of information
- If the query is a simple greeting or doesn't need external info, set shouldUseTool to false
- For ambiguous queries, prefer qdrant_search first (knowledge base), then linkup_search (web)
- Always provide clear reasoning for your selections
- Set priority higher for tools that are more central to answering the query

Examples:
- "What's in my documents about machine learning?" → qdrant_search only
- "What happened in the news today?" → linkup_search only
- "Compare what my docs say about X with current best practices" → both tools
- "Analyze this image: [url]" → image_analysis
- "Hello, how are you?" → shouldUseTool: false`;

/**
 * User prompt for tool routing
 */
function createToolRouterPrompt(query: string, context?: string): string {
  let prompt = `Query: "${query}"`;

  if (context) {
    prompt += `\n\nAdditional context:\n${context}`;
  }

  prompt += `

Analyze this query and decide which tools (if any) should be used.
Return your selection with appropriate inputs for each tool.`;

  return prompt;
}

/**
 * Route query to appropriate tools using LLM
 */
export async function routeToTools(
  query: string,
  context?: string
): Promise<ToolRoutingDecision> {
  const log = logger.child({ component: "tool-router" });
  log.debug("Routing query to tools", { query: query.slice(0, 100) });

  try {
    const result = await generateJSON<ToolSelectionResult>({
      tier: "cheap",
      system: TOOL_ROUTER_SYSTEM,
      prompt: createToolRouterPrompt(query, context),
      schema: ToolSelectionSchema,
    });

    log.info("Tool routing complete", {
      shouldUseTool: result.shouldUseTool,
      selectedTools: result.selectedTools.map((t) => t.name),
      confidence: result.confidence,
    });

    return {
      shouldUseTool: result.shouldUseTool,
      selectedTools: result.selectedTools as ToolSelection[],
      reasoning: result.reasoning,
      confidence: result.confidence,
    };
  } catch (error) {
    log.error("Tool routing failed, falling back to heuristics", error as Error);
    return routeToToolsSimple(query);
  }
}

/**
 * Simple heuristic-based tool routing (fallback)
 */
export function routeToToolsSimple(query: string): ToolRoutingDecision {
  const lowerQuery = query.toLowerCase();
  const selectedTools: ToolSelection[] = [];

  // Check for image indicators
  const hasImage =
    lowerQuery.includes("image") ||
    lowerQuery.includes("picture") ||
    lowerQuery.includes("photo") ||
    query.includes("http") && (query.includes(".png") || query.includes(".jpg") || query.includes(".jpeg") || query.includes(".gif") || query.includes(".webp"));

  if (hasImage) {
    // Extract URL if present
    const urlMatch = query.match(/https?:\/\/[^\s]+/);
    selectedTools.push({
      name: ToolName.IMAGE_ANALYSIS,
      priority: 10,
      input: {
        imageUrl: urlMatch?.[0],
        prompt: query,
        extractText: lowerQuery.includes("text") || lowerQuery.includes("read") || lowerQuery.includes("ocr"),
      },
      reasoning: "Query involves image analysis",
    });
  }

  // Check for real-time/web indicators
  const needsWeb =
    lowerQuery.includes("today") ||
    lowerQuery.includes("latest") ||
    lowerQuery.includes("current") ||
    lowerQuery.includes("now") ||
    lowerQuery.includes("news") ||
    lowerQuery.includes("recent") ||
    lowerQuery.includes("2025") ||
    lowerQuery.includes("search the web") ||
    lowerQuery.includes("look up");

  if (needsWeb) {
    selectedTools.push({
      name: ToolName.LINKUP_SEARCH,
      priority: 8,
      input: {
        query: query,
        depth: lowerQuery.includes("deep") ? "deep" : "standard",
        outputType: "searchResults",
      },
      reasoning: "Query requires real-time or current information",
    });
  }

  // Check for knowledge base indicators
  const needsKnowledge =
    lowerQuery.includes("document") ||
    lowerQuery.includes("knowledge") ||
    lowerQuery.includes("my data") ||
    lowerQuery.includes("ingested") ||
    lowerQuery.includes("uploaded") ||
    lowerQuery.includes("in my") ||
    !needsWeb; // Default to knowledge base if no web indicators

  if (needsKnowledge && !hasImage) {
    selectedTools.push({
      name: ToolName.QDRANT_SEARCH,
      priority: needsWeb ? 6 : 9, // Lower priority if web is also being used
      input: {
        query: query,
        mode: "hybrid",
        topK: 20,
      },
      reasoning: "Query can be answered from knowledge base",
    });
  }

  // Check for greetings/simple queries
  const isSimpleQuery =
    /^(hi|hello|hey|good morning|good afternoon|thanks|thank you|bye|goodbye)[\s!?.]*$/i.test(query.trim());

  if (isSimpleQuery) {
    return {
      shouldUseTool: false,
      selectedTools: [],
      reasoning: "Simple greeting or acknowledgment - no tools needed",
      confidence: 0.95,
    };
  }

  return {
    shouldUseTool: selectedTools.length > 0,
    selectedTools: selectedTools.sort((a, b) => b.priority - a.priority),
    reasoning: `Heuristic routing based on query analysis. Selected ${selectedTools.length} tool(s).`,
    confidence: 0.7,
  };
}

/**
 * Determine if we should use the web for this query
 * Quick check without full routing
 */
export function shouldUseWeb(query: string): boolean {
  const lowerQuery = query.toLowerCase();
  return (
    lowerQuery.includes("today") ||
    lowerQuery.includes("latest") ||
    lowerQuery.includes("current") ||
    lowerQuery.includes("now") ||
    lowerQuery.includes("news") ||
    lowerQuery.includes("recent") ||
    lowerQuery.includes("2025") ||
    lowerQuery.includes("search the web")
  );
}

/**
 * Determine if query involves images
 */
export function hasImageContent(query: string): boolean {
  return (
    query.toLowerCase().includes("image") ||
    query.toLowerCase().includes("picture") ||
    /https?:\/\/[^\s]+\.(png|jpg|jpeg|gif|webp)/i.test(query)
  );
}
