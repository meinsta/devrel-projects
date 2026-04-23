import { z } from "zod";
import { generateJSON } from "@/lib/llm/client";
import { CRITIC_SYSTEM, CRITIC_USER } from "@/lib/llm/prompts";
import { logger } from "@/lib/shared/logger";
import type { EvidenceCritique, SubQuery } from "./types";
import type { RetrievedChunk } from "@/lib/retrieval/types";

const CritiqueSchema = z.object({
  coverageScore: z.number().min(0).max(1),
  consistencyScore: z.number().min(0).max(1),
  specificityScore: z.number().min(0).max(1),
  reasoning: z.string(),
  missingIntents: z.array(z.string()),
  contradictions: z.array(z.string()),
});

/**
 * Confidence thresholds for decision making
 */
export const CONFIDENCE_THRESHOLDS = {
  PASS: 0.72,        // Answer now
  RETRY: 0.55,       // Try corrective action
  // Below RETRY: Structured fallback (not implemented in MVP)
};

/**
 * Weights for computing overall confidence
 */
const CONFIDENCE_WEIGHTS = {
  rerankScore: 0.3,
  coverage: 0.25,
  specificity: 0.25,
  consistency: 0.2,
};

/**
 * Critique the quality of retrieved evidence
 */
export async function critiqueEvidence(
  query: string,
  subQueries: SubQuery[],
  chunks: RetrievedChunk[]
): Promise<EvidenceCritique> {
  logger.debug("Critiquing evidence", { numChunks: chunks.length });

  // Prepare chunk summaries for the critic
  const chunkSummaries = chunks.slice(0, 15).map((c, i) => {
    const preview = c.payload.text.slice(0, 300).replace(/\n/g, " ");
    return `[${i}] ${c.payload.title || "Untitled"}: ${preview}...`;
  });

  const subQueryTexts = subQueries.map((q) => q.text);

  const result = await generateJSON({
    tier: "cheap",
    system: CRITIC_SYSTEM,
    prompt: CRITIC_USER(query, subQueryTexts, chunkSummaries),
    schema: CritiqueSchema,
  });

  // Compute overall confidence score
  const avgRerankScore = chunks.length > 0
    ? chunks.slice(0, 10).reduce((sum, c) => sum + c.score, 0) / Math.min(chunks.length, 10)
    : 0;

  const overallConfidence =
    CONFIDENCE_WEIGHTS.rerankScore * avgRerankScore +
    CONFIDENCE_WEIGHTS.coverage * result.coverageScore +
    CONFIDENCE_WEIGHTS.specificity * result.specificityScore +
    CONFIDENCE_WEIGHTS.consistency * result.consistencyScore;

  const critique: EvidenceCritique = {
    coverageScore: result.coverageScore,
    consistencyScore: result.consistencyScore,
    specificityScore: result.specificityScore,
    overallConfidence,
    reasoning: result.reasoning,
    missingIntents: result.missingIntents,
    contradictions: result.contradictions,
  };

  logger.debug("Critique result", {
    overallConfidence,
    coverage: result.coverageScore,
    consistency: result.consistencyScore,
    specificity: result.specificityScore,
  });

  return critique;
}

/**
 * Simple heuristic critique (fallback, no LLM call)
 */
export function critiqueEvidenceSimple(
  chunks: RetrievedChunk[]
): EvidenceCritique {
  // No chunks = no evidence
  if (chunks.length === 0) {
    return {
      coverageScore: 0,
      consistencyScore: 1, // No contradictions if no evidence
      specificityScore: 0,
      overallConfidence: 0,
      reasoning: "No evidence retrieved",
      missingIntents: ["all"],
      contradictions: [],
    };
  }

  // Use rerank scores as proxy for quality
  const scores = chunks.slice(0, 10).map((c) => c.score);
  const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
  const topScore = Math.max(...scores);

  // Heuristic scoring
  const specificityScore = avgScore;
  const coverageScore = Math.min(chunks.length / 10, 1) * 0.7 + avgScore * 0.3;
  const consistencyScore = 0.8; // Assume consistent without LLM check

  const overallConfidence =
    CONFIDENCE_WEIGHTS.rerankScore * avgScore +
    CONFIDENCE_WEIGHTS.coverage * coverageScore +
    CONFIDENCE_WEIGHTS.specificity * specificityScore +
    CONFIDENCE_WEIGHTS.consistency * consistencyScore;

  return {
    coverageScore,
    consistencyScore,
    specificityScore,
    overallConfidence,
    reasoning: `Heuristic: avg_score=${avgScore.toFixed(2)}, top_score=${topScore.toFixed(2)}, count=${chunks.length}`,
    missingIntents: [],
    contradictions: [],
  };
}

/**
 * Check if evidence passes confidence threshold
 */
export function shouldProceedToAnswer(critique: EvidenceCritique): boolean {
  return critique.overallConfidence >= CONFIDENCE_THRESHOLDS.PASS;
}

/**
 * Check if we should retry with corrections
 */
export function shouldRetryWithCorrection(
  critique: EvidenceCritique,
  loopCount: number,
  maxLoops: number
): boolean {
  return (
    critique.overallConfidence >= CONFIDENCE_THRESHOLDS.RETRY &&
    critique.overallConfidence < CONFIDENCE_THRESHOLDS.PASS &&
    loopCount < maxLoops
  );
}
