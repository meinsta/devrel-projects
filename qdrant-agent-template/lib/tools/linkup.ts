import { env } from "@/lib/shared/env";
import { logger } from "@/lib/shared/logger";
import {
  LinkupSearchInputSchema,
  LinkupSearchResultSchema,
  type ToolDefinition,
  type LinkupSearchInput,
  type LinkupSearchResult,
} from "./types";

/**
 * Linkup Web Search Client
 * Uses the linkup-sdk for direct API access
 */
class LinkupClient {
  private apiKey: string;
  private baseUrl = "https://api.linkup.so/v1";

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async search(input: LinkupSearchInput): Promise<LinkupSearchResult> {
    const startTime = Date.now();

    try {
      const response = await fetch(`${this.baseUrl}/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({
          q: input.query,
          depth: input.depth,
          outputType: input.outputType,
        }),
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Linkup API error: ${response.status} - ${error}`);
      }

      const data = await response.json();

      logger.info("Linkup search completed", {
        query: input.query.slice(0, 50),
        depth: input.depth,
        latencyMs: Date.now() - startTime,
        resultCount: data.results?.length || 0,
      });

      // Transform to our schema
      return {
        results: (data.results || []).map((r: Record<string, unknown>) => ({
          title: r.name || r.title || "",
          url: r.url || "",
          snippet: r.snippet || "",
          content: r.content || undefined,
        })),
        answer: data.answer || undefined,
      };
    } catch (error) {
      logger.error("Linkup search failed", error as Error);
      throw error;
    }
  }
}

let client: LinkupClient | null = null;

function getClient(): LinkupClient {
  if (!client) {
    const apiKey = env.LINKUP_API_KEY;
    if (!apiKey) {
      throw new Error("LINKUP_API_KEY not configured");
    }
    client = new LinkupClient(apiKey);
  }
  return client;
}

/**
 * Execute Linkup web search
 */
export async function executeLinkupSearch(
  input: LinkupSearchInput
): Promise<LinkupSearchResult> {
  return getClient().search(input);
}

/**
 * Linkup Search Tool Definition
 */
export const linkupSearchTool: ToolDefinition<LinkupSearchInput, LinkupSearchResult> = {
  name: "linkup_search",
  description: `Search the web for real-time information. Use this when:
- The query asks about current events, news, or recent information
- The knowledge base doesn't have up-to-date information
- The user explicitly asks to search the web
- You need to verify facts with current sources
Supports depths: "basic" (fast), "standard" (balanced), "deep" (thorough, agentic)`,
  category: "web",
  inputSchema: LinkupSearchInputSchema,
  outputSchema: LinkupSearchResultSchema,
  execute: executeLinkupSearch,
};

/**
 * Get Linkup tool for Vercel AI SDK tool calling
 * This can be passed directly to generateText/streamText
 */
export function getLinkupToolForAI() {
  return {
    linkup_search: {
      description: linkupSearchTool.description,
      parameters: LinkupSearchInputSchema,
      execute: async (input: LinkupSearchInput) => {
        const result = await executeLinkupSearch(input);
        // Return formatted for LLM consumption
        return {
          webResults: result.results.map((r, i) => ({
            index: i + 1,
            title: r.title,
            url: r.url,
            snippet: r.snippet,
          })),
          synthesizedAnswer: result.answer,
        };
      },
    },
  };
}
