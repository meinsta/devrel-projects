import { NextRequest } from "next/server";
import { z } from "zod";
import { addTraceFeedback } from "@/lib/traces/store";
import { writeMemoriesFromInteraction } from "@/lib/memory/store";
import { errorResponse, ValidationError, NotFoundError } from "@/lib/shared/errors";
import { logger } from "@/lib/shared/logger";

const RequestSchema = z.object({
  traceId: z.string().min(1),
  rating: z.enum(["positive", "negative"]),
  comment: z.string().max(1000).optional(),
  // Optional: for memory extraction
  userId: z.string().optional(),
  query: z.string().optional(),
  answer: z.string().optional(),
});

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const parsed = RequestSchema.safeParse(body);

    if (!parsed.success) {
      throw new ValidationError(parsed.error.errors[0].message);
    }

    const { traceId, rating, comment, userId, query, answer } = parsed.data;

    logger.info("Feedback request", { traceId, rating });

    // Add feedback to trace
    const updated = await addTraceFeedback(traceId, { rating, comment });

    if (!updated) {
      throw new NotFoundError(`Trace ${traceId} not found`);
    }

    // If positive feedback and we have the interaction details, extract memories
    let memoriesWritten = 0;
    if (rating === "positive" && userId && query && answer) {
      memoriesWritten = await writeMemoriesFromInteraction(
        userId,
        traceId,
        query,
        answer,
        0.8 // Treat user confirmation as high confidence
      );
    }

    return Response.json({
      success: true,
      traceId,
      rating,
      memoriesWritten,
    });
  } catch (error) {
    return errorResponse(error);
  }
}
