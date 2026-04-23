import type { DebugReport } from "@/lib/agent/types";

/**
 * Trace status
 */
export type TraceStatus = "running" | "completed" | "error";

/**
 * Stored trace record
 */
export interface TraceRecord extends DebugReport {
  userId?: string;
  feedback?: {
    rating: "positive" | "negative";
    comment?: string;
    createdAt: string;
  };
}

/**
 * Trace query filters
 */
export interface TraceQueryFilters {
  userId?: string;
  status?: TraceStatus;
  startDate?: string;
  endDate?: string;
}

/**
 * Trace list options
 */
export interface TraceListOptions {
  filters?: TraceQueryFilters;
  limit?: number;
  offset?: number;
}
