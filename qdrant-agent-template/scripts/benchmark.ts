import "dotenv/config";
import { search } from "../lib/retrieval/search";
import type { SearchParams, RetrievalMode, RetrievedChunk } from "../lib/retrieval/types";
import { readFile } from "fs/promises";

/**
 * Benchmark retrieval performance on SQuAD questions
 * Measures: Recall@K, MRR, Latency
 */

interface BenchmarkQuestion {
  id: string;
  question: string;
  answer: string;
  docId: string;
  articleTitle: string;
}

interface BenchmarkResult {
  mode: string;
  totalQuestions: number;
  recall: {
    at1: number;
    at5: number;
    at10: number;
  };
  mrr: number;
  avgLatencyMs: number;
  p95LatencyMs: number;
}

async function loadQuestions(): Promise<BenchmarkQuestion[]> {
  const data = await readFile("./scripts/benchmark-questions.json", "utf-8");
  return JSON.parse(data);
}

function checkHit(
  results: RetrievedChunk[],
  question: BenchmarkQuestion,
  topK: number
): boolean {
  // Check if any of the top K results contain the answer or are from the right doc
  return results.slice(0, topK).some((r) => {
    // Check doc ID match
    if (r.payload.doc_id === question.docId) return true;
    // Check if answer text appears in the chunk
    if (r.payload.text.toLowerCase().includes(question.answer.toLowerCase())) return true;
    // Check title match (article name)
    if (r.payload.title?.includes(question.articleTitle)) return true;
    return false;
  });
}

function findFirstHitRank(
  results: RetrievedChunk[],
  question: BenchmarkQuestion
): number {
  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    if (
      r.payload.doc_id === question.docId ||
      r.payload.text.toLowerCase().includes(question.answer.toLowerCase()) ||
      r.payload.title?.includes(question.articleTitle)
    ) {
      return i + 1; // 1-indexed rank
    }
  }
  return 0; // Not found
}

// Sleep helper
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

async function runBenchmark(
  questions: BenchmarkQuestion[],
  mode: RetrievalMode,
  modeName: string
): Promise<BenchmarkResult> {
  console.log(`\nRunning benchmark: ${modeName}`);
  console.log(`Questions: ${questions.length}`);

  const latencies: number[] = [];
  let hitsAt1 = 0;
  let hitsAt5 = 0;
  let hitsAt10 = 0;
  let sumReciprocalRank = 0;

  for (let i = 0; i < questions.length; i++) {
    const q = questions[i];

    const searchParams: SearchParams = {
      query: q.question,
      mode,
      topK: 10,
    };

    // Rate limit: ~60 requests/minute to stay under 100 limit
    if (i > 0) {
      await sleep(700);
    }

    const startTime = performance.now();
    const results = await search(searchParams);
    const latencyMs = performance.now() - startTime;
    latencies.push(latencyMs);

    if (checkHit(results, q, 1)) hitsAt1++;
    if (checkHit(results, q, 5)) hitsAt5++;
    if (checkHit(results, q, 10)) hitsAt10++;

    const rank = findFirstHitRank(results, q);
    if (rank > 0) {
      sumReciprocalRank += 1 / rank;
    }

    // Progress update
    if ((i + 1) % 5 === 0) {
      process.stdout.write(`  Processed ${i + 1}/${questions.length}\r`);
    }
  }

  // Calculate metrics
  const n = questions.length;
  latencies.sort((a, b) => a - b);

  return {
    mode: modeName,
    totalQuestions: n,
    recall: {
      at1: hitsAt1 / n,
      at5: hitsAt5 / n,
      at10: hitsAt10 / n,
    },
    mrr: sumReciprocalRank / n,
    avgLatencyMs: latencies.reduce((a, b) => a + b, 0) / n,
    p95LatencyMs: latencies[Math.floor(n * 0.95)],
  };
}

function printResults(results: BenchmarkResult[]) {
  console.log("\n" + "=".repeat(70));
  console.log("BENCHMARK RESULTS");
  console.log("=".repeat(70));

  console.log("\n┌─────────────────┬──────────┬──────────┬──────────┬─────────┬──────────┬──────────┐");
  console.log("│ Mode            │ R@1      │ R@5      │ R@10     │ MRR     │ Avg(ms)  │ P95(ms)  │");
  console.log("├─────────────────┼──────────┼──────────┼──────────┼─────────┼──────────┼──────────┤");

  for (const r of results) {
    console.log(
      `│ ${r.mode.padEnd(15)} │ ${(r.recall.at1 * 100).toFixed(1).padStart(6)}%  │ ${(r.recall.at5 * 100).toFixed(1).padStart(6)}%  │ ${(r.recall.at10 * 100).toFixed(1).padStart(6)}%  │ ${r.mrr.toFixed(3).padStart(6)}  │ ${r.avgLatencyMs.toFixed(0).padStart(6)}   │ ${r.p95LatencyMs.toFixed(0).padStart(6)}   │`
    );
  }

  console.log("└─────────────────┴──────────┴──────────┴──────────┴─────────┴──────────┴──────────┘");
  console.log("\nR@K = Recall at K (% of queries where relevant doc is in top K)");
  console.log("MRR = Mean Reciprocal Rank");
}

async function main() {
  const args = process.argv.slice(2);
  const maxQuestions = parseInt(args[0] || "50", 10);

  console.log("Loading benchmark questions...");
  let questions = await loadQuestions();
  questions = questions.slice(0, maxQuestions);
  console.log(`Using ${questions.length} questions`);

  const results: BenchmarkResult[] = [];

  // Test different search modes
  const modes: Array<{ name: string; mode: RetrievalMode }> = [
    { name: "Dense", mode: "dense" },
    { name: "Sparse", mode: "sparse" },
    { name: "Hybrid", mode: "hybrid" },
  ];

  for (const { name, mode } of modes) {
    try {
      const result = await runBenchmark(questions, mode, name);
      results.push(result);
    } catch (error) {
      console.error(`Failed to run ${name}:`, error);
    }
  }

  printResults(results);
}

main().catch((error) => {
  console.error("Benchmark failed:", error);
  process.exit(1);
});
