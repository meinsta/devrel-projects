/**
 * Agent Module
 * Exports agent orchestrators and related types
 */

// Original orchestrator (v1)
export { AgentOrchestrator, runAgent, type AgentConfig } from "./orchestrator";

// Enhanced orchestrator with tool calling (v2)
export {
  AgentOrchestratorV2,
  runAgentV2,
  type AgentConfigV2,
  type AgentStateV2,
  type AgentContextV2,
  type AgentEventV2,
} from "./orchestrator-v2";

// Types
export type {
  AgentState,
  AgentContext,
  AgentEvent,
  RouteDecision,
  SubQuery,
  QueryBundle,
  EvidenceCritique,
  CorrectiveAction,
  Citation,
  UserContext,
  DebugReport,
} from "./types";

// Sub-modules
export { routeQuery, routeQuerySimple } from "./router";
export { planQueries, planQueriesSimple, createQueryBundle } from "./planner";
export { critiqueEvidence, shouldProceedToAnswer, shouldRetryWithCorrection } from "./critic";
export { decideCorrectiveAction, decideCorrectiveActionSimple, applyCorrectiveAction } from "./corrective";
