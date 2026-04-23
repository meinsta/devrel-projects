import { NextRequest } from "next/server";
import { z } from "zod";
import { search } from "@/lib/retrieval/search";
import { rerankChunks } from "@/lib/retrieval/reranker";
import { errorResponse, ValidationError } from "@/lib/shared/errors";
import { logger } from "@/lib/shared/logger";

const RequestSchema = z.object({
  query: z.string().min(1).max(5000),
  mode: z.enum(["dense", "sparse", "hybrid"]).default("hybrid"),
  topK: z.number().min(1).max(100).default(20),
  rerank: z.boolean().default(true),
  rerankTopN: z.number().min(1).max(50).default(10),
  filters: z.object({
    source: z.array(z.string()).optional(),
    tags: z.array(z.string()).optional(),
    accessScope: z.string().optional(),
    docId: z.string().optional(),
  }).optional(),
});

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const parsed = RequestSchema.safeParse(body);

    if (!parsed.success) {
      throw new ValidationError(parsed.error.errors[0].message);
    }

    const { query, mode, topK, rerank, rerankTopN, filters } = parsed.data;

    logger.info("Search request", { query: query.slice(0, 50), mode, topK });

    // Search
    const results = await search({
      query,
      mode,
      topK: rerank ? Math.max(topK * 3, 50) : topK,
      filters,
    });

    // Rerank if enabled
    let finalResults = results;
    if (rerank && results.length > 0) {
      const reranked = await rerankChunks(
        query,
        results.map((r) => ({ id: r.id, text: r.payload.text })),
        rerankTopN
      );

      finalResults = reranked.map((r) => ({
        ...results[r.originalIndex],
        score: r.score,
      }));
    } else {
      finalResults = results.slice(0, topK);
    }

    return Response.json({
      results: finalResults.map((r) => ({
        id: r.id,
        score: r.score,
        docId: r.payload.doc_id,
        title: r.payload.title,
        text: r.payload.text,
        source: r.payload.source,
        url: r.payload.url,
        tags: r.payload.tags,
      })),
      query,
      mode,
      count: finalResults.length,
    });
  } catch (error) {
    return errorResponse(error);
  }
}
