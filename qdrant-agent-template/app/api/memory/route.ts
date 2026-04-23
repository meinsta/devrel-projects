import { NextRequest } from "next/server";
import { z } from "zod";
import { createMemory, listMemories, searchMemories, deleteUserMemories } from "@/lib/memory/store";
import { errorResponse, ValidationError } from "@/lib/shared/errors";
import { logger } from "@/lib/shared/logger";

const CreateMemorySchema = z.object({
  userId: z.string().min(1),
  type: z.enum(["episodic", "preference", "fact"]),
  content: z.string().min(1).max(2000),
  metadata: z.object({
    confidence: z.number().min(0).max(1).default(0.8),
    source: z.string().optional(),
    tags: z.array(z.string()).optional(),
  }).optional(),
});

const SearchMemorySchema = z.object({
  userId: z.string().min(1),
  query: z.string().min(1).max(1000),
  types: z.array(z.enum(["episodic", "preference", "fact"])).optional(),
  limit: z.number().min(1).max(50).default(10),
  minConfidence: z.number().min(0).max(1).default(0),
});

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Check if this is a search or create request
    if (body.query && body.userId) {
      // Search request
      const parsed = SearchMemorySchema.safeParse(body);
      if (!parsed.success) {
        throw new ValidationError(parsed.error.errors[0].message);
      }

      const { userId, query, types, limit, minConfidence } = parsed.data;

      logger.debug("Memory search request", { userId, query: query.slice(0, 50) });

      const memories = await searchMemories(query, {
        userId,
        types,
        limit,
        minConfidence,
      });

      return Response.json({
        memories: memories.map((m) => ({
          id: m.id,
          type: m.type,
          content: m.content,
          confidence: m.metadata.confidence,
          createdAt: m.createdAt,
        })),
        count: memories.length,
      });
    }

    // Create request
    const parsed = CreateMemorySchema.safeParse(body);
    if (!parsed.success) {
      throw new ValidationError(parsed.error.errors[0].message);
    }

    const { userId, type, content, metadata } = parsed.data;

    logger.info("Create memory request", { userId, type });

    const memory = await createMemory({
      userId,
      type,
      content,
      metadata,
    });

    return Response.json({
      success: true,
      memory: {
        id: memory.id,
        type: memory.type,
        content: memory.content,
        createdAt: memory.createdAt,
      },
    });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const userId = searchParams.get("userId");
    const types = searchParams.get("types")?.split(",") as ("episodic" | "preference" | "fact")[] | undefined;
    const limit = parseInt(searchParams.get("limit") || "50", 10);

    if (!userId) {
      throw new ValidationError("userId is required");
    }

    logger.debug("List memories request", { userId });

    const memories = await listMemories(userId, { types, limit });

    return Response.json({
      memories: memories.map((m) => ({
        id: m.id,
        type: m.type,
        content: m.content,
        confidence: m.metadata.confidence,
        createdAt: m.createdAt,
        accessCount: m.accessCount,
      })),
      count: memories.length,
    });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const userId = searchParams.get("userId");

    if (!userId) {
      throw new ValidationError("userId is required");
    }

    logger.info("Delete all memories request", { userId });

    const deleted = await deleteUserMemories(userId);

    return Response.json({
      success: true,
      deleted,
    });
  } catch (error) {
    return errorResponse(error);
  }
}
