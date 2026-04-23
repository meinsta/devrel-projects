import type { RetrievedChunk } from "./types";

/**
 * Reciprocal Rank Fusion (RRF)
 * Combines multiple ranked lists into a single ranking
 *
 * Formula: RRF(d) = Σ 1/(k + rank(d))
 * where k is a constant (default 60) and rank(d) is the position in each list
 */
export function rrfFusion(
  resultSets: RetrievedChunk[][],
  k: number = 60,
  weights?: number[]
): RetrievedChunk[] {
  const scores = new Map<string, { score: number; chunk: RetrievedChunk }>();

  resultSets.forEach((results, setIndex) => {
    const weight = weights?.[setIndex] ?? 1;

    results.forEach((chunk, rank) => {
      const rrfScore = weight / (k + rank + 1);
      const existing = scores.get(chunk.id);

      if (existing) {
        existing.score += rrfScore;
      } else {
        scores.set(chunk.id, { score: rrfScore, chunk });
      }
    });
  });

  return Array.from(scores.values())
    .sort((a, b) => b.score - a.score)
    .map(({ score, chunk }) => ({ ...chunk, score }));
}

/**
 * Deduplicate chunks by hash
 * Removes near-duplicate content
 */
export function deduplicateByHash(chunks: RetrievedChunk[]): RetrievedChunk[] {
  const seen = new Set<string>();
  return chunks.filter((chunk) => {
    if (seen.has(chunk.payload.hash)) {
      return false;
    }
    seen.add(chunk.payload.hash);
    return true;
  });
}

/**
 * Deduplicate by document ID with a cap per document
 * Ensures diversity in results
 */
export function deduplicateByDoc(
  chunks: RetrievedChunk[],
  maxPerDoc: number = 3
): RetrievedChunk[] {
  const docCounts = new Map<string, number>();

  return chunks.filter((chunk) => {
    const docId = chunk.payload.doc_id;
    const count = docCounts.get(docId) ?? 0;

    if (count >= maxPerDoc) {
      return false;
    }

    docCounts.set(docId, count + 1);
    return true;
  });
}

/**
 * Full deduplication pipeline
 */
export function deduplicate(
  chunks: RetrievedChunk[],
  options: { maxPerDoc?: number; byHash?: boolean } = {}
): RetrievedChunk[] {
  const { maxPerDoc = 3, byHash = true } = options;

  let result = chunks;

  if (byHash) {
    result = deduplicateByHash(result);
  }

  result = deduplicateByDoc(result, maxPerDoc);

  return result;
}

/**
 * Group chunks by query index (for analysis)
 */
export function groupByQuery(chunks: RetrievedChunk[]): Map<number, RetrievedChunk[]> {
  const groups = new Map<number, RetrievedChunk[]>();

  for (const chunk of chunks) {
    const queryIndex = chunk.queryIndex ?? 0;
    const group = groups.get(queryIndex) ?? [];
    group.push(chunk);
    groups.set(queryIndex, group);
  }

  return groups;
}

/**
 * Calculate hit rate per query
 * Returns the number of chunks retrieved per sub-query
 */
export function calculateHitRates(
  chunks: RetrievedChunk[],
  numQueries: number
): number[] {
  const groups = groupByQuery(chunks);
  const rates: number[] = [];

  for (let i = 0; i < numQueries; i++) {
    rates.push(groups.get(i)?.length ?? 0);
  }

  return rates;
}
