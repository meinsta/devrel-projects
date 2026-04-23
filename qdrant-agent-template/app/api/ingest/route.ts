import { NextRequest } from "next/server";
import { z } from "zod";
import { ingestDocument, ingestDocuments, deleteDocument, listDocuments } from "@/lib/ingestion/pipeline";
import { errorResponse, ValidationError } from "@/lib/shared/errors";
import { logger } from "@/lib/shared/logger";

const DocumentSchema = z.object({
  id: z.string().optional(),
  content: z.string().min(1),
  metadata: z.object({
    source: z.string().min(1),
    title: z.string().optional(),
    url: z.string().url().optional(),
    filename: z.string().optional(),
    format: z.enum(["markdown", "html", "code", "text"]).optional(),
    accessScope: z.string().default("public"),
    tags: z.array(z.string()).optional(),
    path: z.string().optional(),
    lang: z.string().optional(),
  }),
});

const RequestSchema = z.object({
  documents: z.array(DocumentSchema).min(1).max(100),
  options: z.object({
    maxTokensPerChunk: z.number().min(100).max(2000).default(500),
    overlapTokens: z.number().min(0).max(200).default(50),
    skipDuplicates: z.boolean().default(true),
  }).optional(),
});

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const parsed = RequestSchema.safeParse(body);

    if (!parsed.success) {
      throw new ValidationError(parsed.error.errors[0].message);
    }

    const { documents, options } = parsed.data;

    logger.info("Ingest request", { documentCount: documents.length });

    const results = await ingestDocuments(documents, options);

    const successful = results.filter((r) => r.status === "success");
    const failed = results.filter((r) => r.status === "error");

    return Response.json({
      success: failed.length === 0,
      ingested: successful.length,
      failed: failed.length,
      results: results.map((r) => ({
        docId: r.docId,
        status: r.status,
        chunkCount: r.chunkCount,
        totalTokens: r.totalTokens,
        error: r.error,
      })),
    });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const docId = searchParams.get("docId");

    if (!docId) {
      throw new ValidationError("docId is required");
    }

    logger.info("Delete document request", { docId });

    const deletedChunks = await deleteDocument(docId);

    if (deletedChunks === 0) {
      return Response.json(
        { error: "Document not found", code: "NOT_FOUND" },
        { status: 404 }
      );
    }

    return Response.json({
      success: true,
      docId,
      deletedChunks,
    });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const source = searchParams.get("source") || undefined;
    const limit = parseInt(searchParams.get("limit") || "100", 10);

    const documents = await listDocuments({ source, limit });

    return Response.json({
      documents,
      count: documents.length,
    });
  } catch (error) {
    return errorResponse(error);
  }
}
