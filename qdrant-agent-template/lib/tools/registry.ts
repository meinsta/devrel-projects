import { z } from "zod";
import {
  ToolName,
  type ToolDefinition,
  type ToolCategory,
  type ToolNameType,
} from "./types";
import { linkupSearchTool, getLinkupToolForAI } from "./linkup";
import { qdrantSearchTool, getQdrantToolForAI } from "./qdrant";
import { imageAnalysisTool, getImageToolForAI } from "./image";

/**
 * Tool Registry
 * Central registry of all available tools
 */
class ToolRegistry {
  private tools: Map<string, ToolDefinition<unknown, unknown>> = new Map();

  constructor() {
    // Register all tools
    this.register(linkupSearchTool);
    this.register(qdrantSearchTool);
    this.register(imageAnalysisTool);
  }

  register<TInput, TOutput>(tool: ToolDefinition<TInput, TOutput>) {
    this.tools.set(tool.name, tool as ToolDefinition<unknown, unknown>);
  }

  get(name: string): ToolDefinition<unknown, unknown> | undefined {
    return this.tools.get(name);
  }

  getAll(): ToolDefinition<unknown, unknown>[] {
    return Array.from(this.tools.values());
  }

  getByCategory(category: ToolCategory): ToolDefinition<unknown, unknown>[] {
    return this.getAll().filter((t) => t.category === category);
  }

  getToolDescriptions(): string {
    return this.getAll()
      .map((t) => `- ${t.name} (${t.category}): ${t.description}`)
      .join("\n");
  }

  /**
   * Get all tools formatted for Vercel AI SDK
   */
  getToolsForAI() {
    return {
      ...getLinkupToolForAI(),
      ...getQdrantToolForAI(),
      ...getImageToolForAI(),
    };
  }
}

// Singleton instance
export const toolRegistry = new ToolRegistry();

/**
 * Tool selection schema for LLM responses
 */
export const ToolSelectionSchema = z.object({
  shouldUseTool: z.boolean().describe("Whether any tool should be used"),
  selectedTools: z.array(
    z.object({
      name: z.enum([
        ToolName.LINKUP_SEARCH,
        ToolName.QDRANT_SEARCH,
        ToolName.IMAGE_ANALYSIS,
      ]).describe("Tool name to use"),
      priority: z.number().min(1).max(10).describe("Priority 1-10, higher = more important"),
      input: z.record(z.unknown()).describe("Input parameters for the tool"),
      reasoning: z.string().describe("Why this tool was selected"),
    })
  ),
  reasoning: z.string().describe("Overall reasoning for tool selection"),
  confidence: z.number().min(0).max(1).describe("Confidence in selection 0-1"),
});

export type ToolSelectionResult = z.infer<typeof ToolSelectionSchema>;

/**
 * Get the list of available tool names
 */
export function getAvailableToolNames(): ToolNameType[] {
  return Object.values(ToolName);
}
