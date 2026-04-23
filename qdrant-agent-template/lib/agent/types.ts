import type { RetrievedChunk, RetrievalMode, SearchFilters } from "@/lib/retrieval/types";

/**
 * Agent state machine states
 */
export type AgentState =
  | "ROUTE"
  | "PLAN_QUERIES"
  | "RETRIEVE"
  | "FUSE"
  | "RERANK"
  | "CRITIQUE_EVIDENCE"
  | "DECIDE_NEXT"
  | "GENERATE_ANSWER"
  | "WRITE_MEMORY"
  | "RETURN"
  | "ERROR";

/**
 * Route decision from router
 */
export interface RouteDecision {
  mode: RetrievalMode;
  corpora: string[];
  filters: SearchFilters;
  budget: RetrievalBudget;
  reasoning: string;
}

/**
 * Sub-query from planner
 */
export interface SubQuery {
  text: string;
  intent: string;
  weight: number;
  filters?: SearchFilters;
}

/**
 * Query bundle (planner output)
 */
export interface QueryBundle {
  originalQuery: string;
  queries: SubQuery[];
  filters: SearchFilters;
  budget: RetrievalBudget;
}

/**
 * Retrieval budget constraints
 */
export interface RetrievalBudget {
  latencyMs: number;
  maxChunks: number;
  maxTokensContext: number;
}

/**
 * Evidence critique result
 */
export interface EvidenceCritique {
  coverageScore: number;
  consistencyScore: number;
  specificityScore: number;
  overallConfidence: number;
  reasoning: string;
  missingIntents: string[];
  contradictions: string[];
}

/**
 * Corrective action types
 */
export type CorrectiveAction =
  | { type: "NONE" }
  | { type: "REWRITE_QUERIES"; newQueries: SubQuery[] }
  | { type: "SWITCH_MODE"; newMode: RetrievalMode }
  | { type: "BROADEN_SCOPE"; removedFilters: string[] }
  | { type: "INCREASE_DEPTH"; newTopK: number };

/**
 * Citation reference
 */
export interface Citation {
  chunkId: string;
  docId: string;
  title: string;
  url?: string;
  span?: string;
}

/**
 * User context for personalization
 */
export interface UserContext {
  userId?: string;
  orgId?: string;
  preferences?: Record<string, unknown>;
  memories?: string[];
}

/**
 * Full agent context (state)
 */
export interface AgentContext {
  // Identifiers
  traceId: string;
  userId?: string;

  // Input
  query: string;
  userContext?: UserContext;

  // Routing
  route?: RouteDecision;

  // Planning
  queryBundle?: QueryBundle;

  // Retrieval
  retrievedChunks: RetrievedChunk[];
  fusedChunks: RetrievedChunk[];
  rerankedChunks: RetrievedChunk[];

  // Critique
  critique?: EvidenceCritique;
  correctiveActions: CorrectiveAction[];

  // Output
  answer?: string;
  citations: Citation[];

  // Control
  loopCount: number;
  maxLoops: number;
  state: AgentState;

  // Observability
  timings: Record<string, number>;
  errors: string[];
}

/**
 * Agent event (for streaming updates)
 */
export type AgentEvent =
  | { type: "state"; state: AgentState }
  | { type: "route"; data: RouteDecision }
  | { type: "plan"; data: SubQuery[] }
  | { type: "retrieve"; data: { count: number; perQuery: number[] } }
  | { type: "fuse"; data: { before: number; after: number } }
  | { type: "rerank"; data: { count: number; topScore: number } }
  | { type: "critique"; data: EvidenceCritique }
  | { type: "corrective"; data: CorrectiveAction }
  | { type: "answer_start"; data: null }
  | { type: "answer_chunk"; data: string }
  | { type: "answer_end"; data: { citations: Citation[] } }
  | { type: "memory"; data: { written: number } }
  | { type: "complete"; data: { traceId: string; answer: string; citations: Citation[] } }
  | { type: "error"; data: { message: string; state: AgentState } };

/**
 * Debug report (trace output)
 */
export interface DebugReport {
  traceId: string;
  query: string;
  route: RouteDecision;
  subQueries: SubQuery[];
  retrievalStats: {
    mode: RetrievalMode;
    chunksRetrieved: number;
    chunksAfterFusion: number;
    chunksAfterRerank: number;
    hitRatesPerQuery: number[];
  };
  critique: EvidenceCritique;
  correctiveActions: CorrectiveAction[];
  finalEvidence: Array<{
    chunkId: string;
    score: number;
    title: string;
  }>;
  timings: Record<string, number>;
  loopCount: number;
  status: "completed" | "error";
  error?: string;
  createdAt: string;
}
