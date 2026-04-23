import { NextRequest } from "next/server";
import { getMemory, deleteMemory } from "@/lib/memory/store";
import { errorResponse, NotFoundError } from "@/lib/shared/errors";
import { logger } from "@/lib/shared/logger";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ memoryId: string }> }
) {
  try {
    const { memoryId } = await params;

    logger.debug("Get memory request", { memoryId });

    const memory = await getMemory(memoryId);

    if (!memory) {
      throw new NotFoundError(`Memory ${memoryId} not found`);
    }

    return Response.json({
      id: memory.id,
      userId: memory.userId,
      type: memory.type,
      content: memory.content,
      metadata: memory.metadata,
      createdAt: memory.createdAt,
      lastAccessedAt: memory.lastAccessedAt,
      accessCount: memory.accessCount,
    });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ memoryId: string }> }
) {
  try {
    const { memoryId } = await params;

    logger.info("Delete memory request", { memoryId });

    const deleted = await deleteMemory(memoryId);

    if (!deleted) {
      throw new NotFoundError(`Memory ${memoryId} not found`);
    }

    return Response.json({ success: true, memoryId });
  } catch (error) {
    return errorResponse(error);
  }
}
