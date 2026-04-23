import { NextRequest } from "next/server";
import { z } from "zod";
import { AgentOrchestrator } from "@/lib/agent/orchestrator";
import { saveTrace } from "@/lib/traces/store";
import { getUserContext } from "@/lib/memory/store";
import { errorResponse, ValidationError } from "@/lib/shared/errors";
import { generateTraceId } from "@/lib/shared/ids";
import { logger } from "@/lib/shared/logger";

const RequestSchema = z.object({
  query: z.string().min(1).max(10000),
  userId: z.string().optional(),
  stream: z.boolean().default(true),
  config: z.object({
    maxLoops: z.number().min(1).max(5).default(3),
    useLLMRouting: z.boolean().default(true),
    useLLMPlanning: z.boolean().default(true),
    useLLMCritique: z.boolean().default(true),
  }).optional(),
});

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const parsed = RequestSchema.safeParse(body);

    if (!parsed.success) {
      throw new ValidationError(parsed.error.errors[0].message);
    }

    const { query, userId, stream, config } = parsed.data;
    const traceId = generateTraceId();

    logger.info("Answer request", { traceId, queryLength: query.length, stream });

    // Get user context if userId provided
    let userContext;
    if (userId) {
      const memories = await getUserContext(userId, query);
      if (memories.length > 0) {
        userContext = { userId, memories };
      }
    }

    // Create orchestrator
    const orchestrator = new AgentOrchestrator(query, {
      traceId,
      userId,
      userContext,
      config,
    });

    if (stream) {
      // Streaming response
      const encoder = new TextEncoder();

      const readable = new ReadableStream({
        async start(controller) {
          try {
            for await (const event of orchestrator.run()) {
              const data = JSON.stringify(event) + "\n";
              controller.enqueue(encoder.encode(`data: ${data}\n`));
            }

            // Save trace
            const report = orchestrator.getDebugReport();
            await saveTrace(report, userId);

            controller.enqueue(encoder.encode("data: [DONE]\n\n"));
            controller.close();
          } catch (error) {
            logger.error("Stream error", error as Error, { traceId });
            controller.error(error);
          }
        },
      });

      return new Response(readable, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
          "X-Trace-Id": traceId,
        },
      });
    }

    // Non-streaming response
    let answer = "";
    let citations: Array<{ chunkId: string; docId: string; title: string; url?: string }> = [];

    for await (const event of orchestrator.run()) {
      if (event.type === "answer_chunk") {
        answer += event.data;
      } else if (event.type === "complete") {
        citations = event.data.citations;
      }
    }

    // Save trace
    const report = orchestrator.getDebugReport();
    await saveTrace(report, userId);

    return Response.json({
      answer,
      citations,
      traceId,
      debugReport: report,
    });
  } catch (error) {
    return errorResponse(error);
  }
}
