import { NextRequest } from "next/server";
import { getTraceByTraceId, deleteTrace } from "@/lib/traces/store";
import { errorResponse, NotFoundError } from "@/lib/shared/errors";
import { logger } from "@/lib/shared/logger";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ traceId: string }> }
) {
  try {
    const { traceId } = await params;

    logger.debug("Get trace request", { traceId });

    const trace = await getTraceByTraceId(traceId);

    if (!trace) {
      throw new NotFoundError(`Trace ${traceId} not found`);
    }

    return Response.json(trace);
  } catch (error) {
    return errorResponse(error);
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ traceId: string }> }
) {
  try {
    const { traceId } = await params;

    logger.info("Delete trace request", { traceId });

    const deleted = await deleteTrace(traceId);

    if (!deleted) {
      throw new NotFoundError(`Trace ${traceId} not found`);
    }

    return Response.json({ success: true, traceId });
  } catch (error) {
    return errorResponse(error);
  }
}
