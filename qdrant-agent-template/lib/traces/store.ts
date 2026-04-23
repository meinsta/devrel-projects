import { getQdrantClient } from "@/lib/retrieval/client";
import { COLLECTIONS } from "@/lib/retrieval/collections";
import { embedder } from "@/lib/retrieval/embedder";
import { generateId } from "@/lib/shared/ids";
import { logger } from "@/lib/shared/logger";
import type { DebugReport } from "@/lib/agent/types";
import type { TraceRecord, TraceListOptions, TraceQueryFilters } from "./types";

/**
 * Save a trace to Qdrant
 */
export async function saveTrace(
  report: DebugReport,
  userId?: string
): Promise<string> {
  const client = getQdrantClient();
  const id = generateId();

  logger.debug("Saving trace", { traceId: report.traceId });

  const record: TraceRecord = {
    ...report,
    userId,
  };

  await client.upsert(COLLECTIONS.AGENT_TRACES, {
    points: [
      {
        id,
        payload: record as unknown as Record<string, unknown>,
        vector: {
          dense: embedder.getDenseQuery(report.query),
        },
      },
    ],
  });

  logger.info("Trace saved", { traceId: report.traceId, pointId: id });
  return id;
}

/**
 * Get a trace by trace ID
 */
export async function getTraceByTraceId(traceId: string): Promise<TraceRecord | null> {
  const client = getQdrantClient();

  const results = await client.scroll(COLLECTIONS.AGENT_TRACES, {
    filter: {
      must: [{ key: "traceId", match: { value: traceId } }],
    },
    limit: 1,
    with_payload: true,
  });

  if (results.points.length === 0) {
    return null;
  }

  return results.points[0].payload as unknown as TraceRecord;
}

/**
 * List traces with filters
 */
export async function listTraces(options: TraceListOptions = {}): Promise<TraceRecord[]> {
  const client = getQdrantClient();
  const { filters = {}, limit = 20, offset = 0 } = options;

  const must: unknown[] = [];

  if (filters.userId) {
    must.push({ key: "userId", match: { value: filters.userId } });
  }

  if (filters.status) {
    must.push({ key: "status", match: { value: filters.status } });
  }

  if (filters.startDate) {
    must.push({ key: "createdAt", range: { gte: filters.startDate } });
  }

  if (filters.endDate) {
    must.push({ key: "createdAt", range: { lte: filters.endDate } });
  }

  const results = await client.scroll(COLLECTIONS.AGENT_TRACES, {
    filter: must.length > 0 ? { must } : undefined,
    limit,
    offset,
    with_payload: true,
  });

  return results.points.map((p) => p.payload as unknown as TraceRecord);
}

/**
 * Search traces by query similarity
 */
export async function searchTraces(
  query: string,
  options: { limit?: number; userId?: string } = {}
): Promise<TraceRecord[]> {
  const client = getQdrantClient();
  const { limit = 10, userId } = options;

  const filter = userId
    ? { must: [{ key: "userId", match: { value: userId } }] }
    : undefined;

  const results = await client.query(COLLECTIONS.AGENT_TRACES, {
    query: embedder.getDenseQuery(query),
    using: "dense",
    limit,
    filter,
    with_payload: true,
  });

  return (results.points || []).map((p) => p.payload as unknown as TraceRecord);
}

/**
 * Add feedback to a trace
 */
export async function addTraceFeedback(
  traceId: string,
  feedback: { rating: "positive" | "negative"; comment?: string }
): Promise<boolean> {
  const client = getQdrantClient();

  // Find the point
  const results = await client.scroll(COLLECTIONS.AGENT_TRACES, {
    filter: {
      must: [{ key: "traceId", match: { value: traceId } }],
    },
    limit: 1,
  });

  if (results.points.length === 0) {
    return false;
  }

  const pointId = results.points[0].id;

  // Update payload with feedback
  await client.setPayload(COLLECTIONS.AGENT_TRACES, {
    points: [pointId],
    payload: {
      feedback: {
        ...feedback,
        createdAt: new Date().toISOString(),
      },
    },
  });

  logger.info("Feedback added", { traceId });
  return true;
}

/**
 * Delete a trace
 */
export async function deleteTrace(traceId: string): Promise<boolean> {
  const client = getQdrantClient();

  const results = await client.scroll(COLLECTIONS.AGENT_TRACES, {
    filter: {
      must: [{ key: "traceId", match: { value: traceId } }],
    },
    limit: 1,
  });

  if (results.points.length === 0) {
    return false;
  }

  await client.delete(COLLECTIONS.AGENT_TRACES, {
    points: [results.points[0].id],
  });

  logger.info("Trace deleted", { traceId });
  return true;
}

/**
 * Get trace statistics
 */
export async function getTraceStats(userId?: string): Promise<{
  total: number;
  completed: number;
  errors: number;
  avgConfidence: number;
}> {
  const client = getQdrantClient();

  const baseFilter = userId
    ? [{ key: "userId", match: { value: userId } }]
    : [];

  // Get all traces
  const allTraces = await client.scroll(COLLECTIONS.AGENT_TRACES, {
    filter: baseFilter.length > 0 ? { must: baseFilter } : undefined,
    limit: 1000,
    with_payload: true,
  });

  const traces = allTraces.points.map((p) => p.payload as unknown as TraceRecord);

  const completed = traces.filter((t) => t.status === "completed").length;
  const errors = traces.filter((t) => t.status === "error").length;
  const confidences = traces
    .filter((t) => t.critique?.overallConfidence !== undefined)
    .map((t) => t.critique.overallConfidence);

  const avgConfidence =
    confidences.length > 0
      ? confidences.reduce((a, b) => a + b, 0) / confidences.length
      : 0;

  return {
    total: traces.length,
    completed,
    errors,
    avgConfidence,
  };
}
