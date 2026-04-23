import { generateStream } from "@/lib/llm/client";
import { ANSWER_SYSTEM } from "@/lib/llm/prompts";
import { logger } from "@/lib/shared/logger";
import { generateTraceId } from "@/lib/shared/ids";
import { search, searchMultiple } from "@/lib/retrieval/search";
import { rrfFusion, deduplicate, calculateHitRates } from "@/lib/retrieval/fusion";
import { rerankChunks } from "@/lib/retrieval/reranker";
import { routeQuery, routeQuerySimple } from "./router";
import { planQueries, planQueriesSimple, createQueryBundle } from "./planner";
import { critiqueEvidence, shouldProceedToAnswer, shouldRetryWithCorrection } from "./critic";
import { decideCorrectiveAction, decideCorrectiveActionSimple, applyCorrectiveAction } from "./corrective";

// Tool imports
import {
  routeToTools,
  executeTools,
  formatToolResultsForLLM,
  mergeToolResults,
  type ToolRoutingDecision,
  type ToolResult,
  type ToolSelection,
} from "@/lib/tools";

import type {
  AgentContext,
  AgentEvent,
  AgentState,
  Citation,
  UserContext,
  DebugReport,
} from "./types";
import type { RetrievedChunk } from "@/lib/retrieval/types";

/**
 * Extended agent state machine with tool calling
 */
export type AgentStateV2 = AgentState | "TOOL_ROUTE" | "TOOL_EXECUTE";

/**
 * Extended agent context with tool support
 */
export interface AgentContextV2 extends Omit<AgentContext, "state"> {
  state: AgentStateV2;
  toolRouting?: ToolRoutingDecision;
  toolResults?: ToolResult[];
  toolEvidence?: string;
}

/**
 * Extended agent event types
 */
export type AgentEventV2 =
  | AgentEvent
  | { type: "tool_route"; data: ToolRoutingDecision }
  | { type: "tool_execute"; data: { tools: string[]; results: ToolResult[] } };

/**
 * Configuration for the agent
 */
export interface AgentConfigV2 {
  maxLoops: number;
  topKPerQuery: number;
  rerankTopN: number;
  useLLMRouting: boolean;
  useLLMPlanning: boolean;
  useLLMCritique: boolean;
  useLLMCorrective: boolean;
  // New tool options
  enableTools: boolean;
  enableWebSearch: boolean;
  enableImageAnalysis: boolean;
  toolFirst: boolean; // Run tools before vector search
}

const DEFAULT_CONFIG: AgentConfigV2 = {
  maxLoops: 3,
  topKPerQuery: 50,
  rerankTopN: 30,
  useLLMRouting: true,
  useLLMPlanning: true,
  useLLMCritique: true,
  useLLMCorrective: true,
  enableTools: true,
  enableWebSearch: true,
  enableImageAnalysis: true,
  toolFirst: true,
};

/**
 * Enhanced Agent Orchestrator with Tool Calling
 * State machine: TOOL_ROUTE → TOOL_EXECUTE → ROUTE → PLAN → RETRIEVE → FUSE → RERANK → CRITIQUE → (CORRECT →) ANSWER
 */
export class AgentOrchestratorV2 {
  private ctx: AgentContextV2;
  private config: AgentConfigV2;
  private log: ReturnType<typeof logger.child>;

  constructor(
    query: string,
    options: {
      traceId?: string;
      userId?: string;
      userContext?: UserContext;
      config?: Partial<AgentConfigV2>;
    } = {}
  ) {
    const traceId = options.traceId || generateTraceId();

    this.config = { ...DEFAULT_CONFIG, ...options.config };
    this.log = logger.child({ traceId });

    this.ctx = {
      traceId,
      userId: options.userId,
      query,
      userContext: options.userContext,
      retrievedChunks: [],
      fusedChunks: [],
      rerankedChunks: [],
      correctiveActions: [],
      citations: [],
      loopCount: 0,
      maxLoops: this.config.maxLoops,
      state: this.config.enableTools ? "TOOL_ROUTE" : "ROUTE",
      timings: {},
      errors: [],
    };

    this.log.info("Agent V2 initialized", { query: query.slice(0, 100), toolsEnabled: this.config.enableTools });
  }

  /**
   * Run the agent and yield events
   */
  async *run(): AsyncGenerator<AgentEventV2> {
    while (this.ctx.state !== "RETURN" && this.ctx.state !== "ERROR") {
      const startTime = Date.now();

      try {
        yield { type: "state", state: this.ctx.state as AgentState };

        switch (this.ctx.state) {
          case "TOOL_ROUTE":
            yield* this.handleToolRoute();
            break;

          case "TOOL_EXECUTE":
            yield* this.handleToolExecute();
            break;

          case "ROUTE":
            yield* this.handleRoute();
            break;

          case "PLAN_QUERIES":
            yield* this.handlePlan();
            break;

          case "RETRIEVE":
            yield* this.handleRetrieve();
            break;

          case "FUSE":
            yield* this.handleFuse();
            break;

          case "RERANK":
            yield* this.handleRerank();
            break;

          case "CRITIQUE_EVIDENCE":
            yield* this.handleCritique();
            break;

          case "DECIDE_NEXT":
            yield* this.handleDecideNext();
            break;

          case "GENERATE_ANSWER":
            yield* this.handleGenerateAnswer();
            break;

          case "WRITE_MEMORY":
            yield* this.handleWriteMemory();
            break;
        }

        this.ctx.timings[this.ctx.state] = Date.now() - startTime;
      } catch (error) {
        this.log.error("State error", error as Error, { state: this.ctx.state });
        this.ctx.errors.push((error as Error).message);
        yield { type: "error", data: { message: (error as Error).message, state: this.ctx.state as AgentState } };
        this.ctx.state = "ERROR";
      }
    }

    // Final event
    if (this.ctx.state === "ERROR") {
      yield {
        type: "error",
        data: { message: this.ctx.errors.join("; "), state: "ERROR" },
      };
    } else {
      yield {
        type: "complete",
        data: {
          traceId: this.ctx.traceId,
          answer: this.ctx.answer || "",
          citations: this.ctx.citations,
        },
      };
    }
  }

  /**
   * TOOL_ROUTE: Decide which tools to use
   */
  private async *handleToolRoute(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Routing to tools");

    const routing = await routeToTools(this.ctx.query, this.ctx.userContext?.memories?.join("\n"));

    this.ctx.toolRouting = routing;
    yield { type: "tool_route", data: routing };

    if (routing.shouldUseTool && routing.selectedTools.length > 0) {
      // Filter tools based on config
      const enabledTools = routing.selectedTools.filter((t) => {
        if (t.name === "linkup_search" && !this.config.enableWebSearch) return false;
        if (t.name === "image_analysis" && !this.config.enableImageAnalysis) return false;
        return true;
      });

      if (enabledTools.length > 0) {
        this.ctx.toolRouting.selectedTools = enabledTools;
        this.ctx.state = "TOOL_EXECUTE";
        return;
      }
    }

    // No tools needed, go to regular routing
    this.ctx.state = "ROUTE";
  }

  /**
   * TOOL_EXECUTE: Run selected tools in parallel
   */
  private async *handleToolExecute(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Executing tools");

    if (!this.ctx.toolRouting || this.ctx.toolRouting.selectedTools.length === 0) {
      this.ctx.state = "ROUTE";
      return;
    }

    const results = await executeTools(this.ctx.toolRouting.selectedTools);
    this.ctx.toolResults = results;

    // Format tool results as context for answer generation
    this.ctx.toolEvidence = formatToolResultsForLLM(results);

    yield {
      type: "tool_execute",
      data: {
        tools: results.map((r) => r.name),
        results,
      },
    };

    // Decide next step based on tool results
    const hasKnowledgeBase = results.some((r) => r.name === "qdrant_search");
    const needsMoreContext = !hasKnowledgeBase && this.ctx.toolRouting.selectedTools.some(
      (t) => t.name !== "qdrant_search"
    );

    if (needsMoreContext) {
      // Also run vector search for additional context
      this.ctx.state = "ROUTE";
    } else {
      // Skip to answer generation if we have enough from tools
      this.ctx.state = "GENERATE_ANSWER";
    }
  }

  /**
   * ROUTE: Determine retrieval strategy
   */
  private async *handleRoute(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Routing query");

    const route = this.config.useLLMRouting
      ? await routeQuery(this.ctx.query, this.ctx.userContext)
      : routeQuerySimple(this.ctx.query);

    this.ctx.route = route;
    yield { type: "route", data: route };
    this.ctx.state = "PLAN_QUERIES";
  }

  /**
   * PLAN_QUERIES: Generate sub-queries
   */
  private async *handlePlan(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Planning queries");

    if (!this.ctx.route) throw new Error("No route decision");

    const queries = this.config.useLLMPlanning
      ? await planQueries(this.ctx.query, this.ctx.route)
      : planQueriesSimple(this.ctx.query);

    this.ctx.queryBundle = createQueryBundle(this.ctx.query, queries, this.ctx.route);
    yield { type: "plan", data: queries };
    this.ctx.state = "RETRIEVE";
  }

  /**
   * RETRIEVE: Execute searches
   */
  private async *handleRetrieve(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Retrieving");

    if (!this.ctx.route || !this.ctx.queryBundle) {
      throw new Error("Missing route or query bundle");
    }

    const results = await searchMultiple(
      this.ctx.queryBundle.queries.map((q) => ({
        text: q.text,
        filters: q.filters || this.ctx.queryBundle!.filters,
      })),
      this.ctx.route.mode,
      this.config.topKPerQuery
    );

    this.ctx.retrievedChunks = results;
    const hitRates = calculateHitRates(results, this.ctx.queryBundle.queries.length);

    yield {
      type: "retrieve",
      data: { count: results.length, perQuery: hitRates },
    };
    this.ctx.state = "FUSE";
  }

  /**
   * FUSE: Combine and deduplicate results
   */
  private async *handleFuse(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Fusing results");

    if (!this.ctx.queryBundle) throw new Error("Missing query bundle");

    // Group by query for RRF
    const queryGroups: RetrievedChunk[][] = [];
    for (let i = 0; i < this.ctx.queryBundle.queries.length; i++) {
      queryGroups.push(
        this.ctx.retrievedChunks.filter((c) => c.queryIndex === i)
      );
    }

    const weights = this.ctx.queryBundle.queries.map((q) => q.weight);
    const fused = rrfFusion(queryGroups, 60, weights);
    const deduped = deduplicate(fused, { maxPerDoc: 3 });

    const before = this.ctx.retrievedChunks.length;
    this.ctx.fusedChunks = deduped;

    yield { type: "fuse", data: { before, after: deduped.length } };
    this.ctx.state = "RERANK";
  }

  /**
   * RERANK: Reorder by relevance
   */
  private async *handleRerank(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Reranking");

    const toRerank = this.ctx.fusedChunks.slice(0, 100);
    const reranked = await rerankChunks(
      this.ctx.query,
      toRerank.map((c) => ({ id: c.id, text: c.payload.text })),
      this.config.rerankTopN
    );

    // Merge rerank scores back
    this.ctx.rerankedChunks = reranked.map((r) => ({
      ...toRerank[r.originalIndex],
      score: r.score,
    }));

    const topScore = this.ctx.rerankedChunks[0]?.score ?? 0;
    yield {
      type: "rerank",
      data: { count: this.ctx.rerankedChunks.length, topScore },
    };
    this.ctx.state = "CRITIQUE_EVIDENCE";
  }

  /**
   * CRITIQUE_EVIDENCE: Evaluate quality
   */
  private async *handleCritique(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Critiquing evidence");

    if (!this.ctx.queryBundle) throw new Error("Missing query bundle");

    const critique = await critiqueEvidence(
      this.ctx.query,
      this.ctx.queryBundle.queries,
      this.ctx.rerankedChunks
    );

    this.ctx.critique = critique;
    yield { type: "critique", data: critique };
    this.ctx.state = "DECIDE_NEXT";
  }

  /**
   * DECIDE_NEXT: Proceed to answer or correct
   */
  private async *handleDecideNext(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Deciding next step");

    if (!this.ctx.critique) throw new Error("Missing critique");

    // If we have tool evidence, be more lenient with thresholds
    const hasToolEvidence = !!this.ctx.toolEvidence;
    const adjustedConfidence = hasToolEvidence
      ? this.ctx.critique.overallConfidence + 0.1
      : this.ctx.critique.overallConfidence;

    if (shouldProceedToAnswer({ ...this.ctx.critique, overallConfidence: adjustedConfidence })) {
      this.log.info("Evidence sufficient, proceeding to answer");
      this.ctx.state = "GENERATE_ANSWER";
      return;
    }

    if (shouldRetryWithCorrection(this.ctx.critique, this.ctx.loopCount, this.ctx.maxLoops)) {
      this.log.info("Evidence insufficient, applying correction", {
        loopCount: this.ctx.loopCount,
      });

      const action = this.config.useLLMCorrective
        ? await decideCorrectiveAction(this.ctx as unknown as AgentContext)
        : decideCorrectiveActionSimple(this.ctx as unknown as AgentContext);

      if (action.type !== "NONE") {
        applyCorrectiveAction(this.ctx as unknown as AgentContext, action);
        yield { type: "corrective", data: action };
        this.ctx.loopCount++;

        // Go back to appropriate state
        this.ctx.state = action.type === "REWRITE_QUERIES" ? "PLAN_QUERIES" : "RETRIEVE";
        return;
      }
    }

    // Exhausted retries or confidence too low - answer anyway
    this.log.warn("Proceeding with suboptimal evidence", {
      confidence: this.ctx.critique.overallConfidence,
      loopCount: this.ctx.loopCount,
    });
    this.ctx.state = "GENERATE_ANSWER";
  }

  /**
   * GENERATE_ANSWER: Create final response
   */
  private async *handleGenerateAnswer(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Generating answer");

    yield { type: "answer_start", data: null };

    // Prepare chunks for answer generation
    const chunks = this.ctx.rerankedChunks.slice(0, 15).map((c, i) => ({
      index: i,
      title: c.payload.title || "Untitled",
      text: c.payload.text,
    }));

    // Build the answer prompt with tool evidence if available
    let contextSection = "";

    if (this.ctx.toolEvidence) {
      contextSection += `## Tool Results\n${this.ctx.toolEvidence}\n\n`;
    }

    if (chunks.length > 0) {
      contextSection += `## Knowledge Base Results\n${chunks.map((c) => `[${c.index + 1}] ${c.title}\n${c.text}`).join("\n\n")}`;
    }

    const answerPrompt = `Question: ${this.ctx.query}

${contextSection}

Provide a comprehensive answer based on the above information. If using knowledge base results, cite them with [n] notation.
If tool results and knowledge base conflict, prefer the most recent/authoritative source and note the discrepancy.`;

    // Stream the answer
    let fullAnswer = "";
    const answerStream = generateStream({
      tier: "strong",
      system: ANSWER_SYSTEM,
      prompt: answerPrompt,
    });

    for await (const chunk of answerStream) {
      fullAnswer += chunk;
      yield { type: "answer_chunk", data: chunk };
    }

    this.ctx.answer = fullAnswer;

    // Build citations
    this.ctx.citations = this.ctx.rerankedChunks.slice(0, 15).map((c) => ({
      chunkId: c.id,
      docId: c.payload.doc_id,
      title: c.payload.title,
      url: c.payload.url,
    }));

    // Add web citations if available
    if (this.ctx.toolResults) {
      for (const result of this.ctx.toolResults) {
        if (result.name === "linkup_search" && result.success) {
          const webOutput = result.output as { results?: Array<{ title: string; url: string }> };
          if (webOutput.results) {
            for (const r of webOutput.results.slice(0, 5)) {
              this.ctx.citations.push({
                chunkId: `web_${r.url}`,
                docId: "web_search",
                title: r.title,
                url: r.url,
              });
            }
          }
        }
      }
    }

    yield { type: "answer_end", data: { citations: this.ctx.citations } };
    this.ctx.state = "WRITE_MEMORY";
  }

  /**
   * WRITE_MEMORY: Store useful information
   */
  private async *handleWriteMemory(): AsyncGenerator<AgentEventV2> {
    this.log.debug("Writing memory");

    // Memory writing will be implemented in the memory store
    // For now, just emit event and move on
    yield { type: "memory", data: { written: 0 } };
    this.ctx.state = "RETURN";
  }

  /**
   * Get debug report for tracing
   */
  getDebugReport(): DebugReport & { toolRouting?: ToolRoutingDecision; toolResults?: ToolResult[] } {
    return {
      traceId: this.ctx.traceId,
      query: this.ctx.query,
      route: this.ctx.route!,
      subQueries: this.ctx.queryBundle?.queries || [],
      retrievalStats: {
        mode: this.ctx.route?.mode || "hybrid",
        chunksRetrieved: this.ctx.retrievedChunks.length,
        chunksAfterFusion: this.ctx.fusedChunks.length,
        chunksAfterRerank: this.ctx.rerankedChunks.length,
        hitRatesPerQuery: calculateHitRates(
          this.ctx.retrievedChunks,
          this.ctx.queryBundle?.queries.length || 0
        ),
      },
      critique: this.ctx.critique!,
      correctiveActions: this.ctx.correctiveActions,
      finalEvidence: this.ctx.rerankedChunks.slice(0, 15).map((c) => ({
        chunkId: c.id,
        score: c.score,
        title: c.payload.title,
      })),
      timings: this.ctx.timings,
      loopCount: this.ctx.loopCount,
      status: this.ctx.state === "ERROR" ? "error" : "completed",
      error: this.ctx.errors.length > 0 ? this.ctx.errors.join("; ") : undefined,
      createdAt: new Date().toISOString(),
      // New fields
      toolRouting: this.ctx.toolRouting,
      toolResults: this.ctx.toolResults,
    };
  }

  /**
   * Get trace ID
   */
  getTraceId(): string {
    return this.ctx.traceId;
  }
}

/**
 * Convenience function to run agent and collect all results
 */
export async function runAgentV2(
  query: string,
  options?: {
    traceId?: string;
    userId?: string;
    userContext?: UserContext;
    config?: Partial<AgentConfigV2>;
  }
): Promise<{
  answer: string;
  citations: Citation[];
  traceId: string;
  debugReport: DebugReport & { toolRouting?: ToolRoutingDecision; toolResults?: ToolResult[] };
}> {
  const agent = new AgentOrchestratorV2(query, options);
  let answer = "";
  let citations: Citation[] = [];

  for await (const event of agent.run()) {
    if (event.type === "answer_chunk") {
      answer += event.data;
    } else if (event.type === "complete") {
      citations = event.data.citations;
    }
  }

  return {
    answer,
    citations,
    traceId: agent.getTraceId(),
    debugReport: agent.getDebugReport(),
  };
}
