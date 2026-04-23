/**
 * Tools Module
 * Provides tool calling capabilities for the agent
 */

// Types
export * from "./types";

// Tool implementations
export { linkupSearchTool, executeLinkupSearch, getLinkupToolForAI } from "./linkup";
export { qdrantSearchTool, executeQdrantSearch, getQdrantToolForAI } from "./qdrant";
export { imageAnalysisTool, executeImageAnalysis, getImageToolForAI } from "./image";

// Registry
export { toolRegistry, ToolSelectionSchema, getAvailableToolNames } from "./registry";
export type { ToolSelectionResult } from "./registry";

// Router
export {
  routeToTools,
  routeToToolsSimple,
  shouldUseWeb,
  hasImageContent,
} from "./router";

// Executor
export {
  executeTools,
  executeToolsSequential,
  formatToolResultsForLLM,
  mergeToolResults,
  hasToolErrors,
  getToolOutput,
} from "./executor";
