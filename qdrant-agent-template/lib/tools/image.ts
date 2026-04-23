import { anthropic } from "@ai-sdk/anthropic";
import { generateText } from "ai";
import { env } from "@/lib/shared/env";
import { logger } from "@/lib/shared/logger";
import {
  ImageAnalysisInputSchema,
  ImageAnalysisResultSchema,
  type ToolDefinition,
  type ImageAnalysisInput,
  type ImageAnalysisResult,
} from "./types";

/**
 * Execute image analysis using Claude's vision capabilities
 */
export async function executeImageAnalysis(
  input: ImageAnalysisInput
): Promise<ImageAnalysisResult> {
  const startTime = Date.now();

  if (!input.imageUrl && !input.imageBase64) {
    throw new Error("Either imageUrl or imageBase64 must be provided");
  }

  try {
    // Build the message content with image
    const imageContent: { type: "image"; image: string }[] = [];

    if (input.imageUrl) {
      imageContent.push({
        type: "image",
        image: input.imageUrl,
      });
    } else if (input.imageBase64) {
      imageContent.push({
        type: "image",
        image: input.imageBase64,
      });
    }

    const systemPrompt = `You are an expert image analyst. Analyze the provided image and respond to the user's request.
${input.extractText ? "Extract any visible text in the image accurately." : ""}
Provide structured observations about the image.`;

    const result = await generateText({
      model: anthropic(env.LLM_CHEAP_MODEL),
      system: systemPrompt,
      messages: [
        {
          role: "user",
          content: [
            ...imageContent,
            { type: "text", text: input.prompt },
          ],
        },
      ],
      maxTokens: 2048,
    });

    // Parse response to extract structured data
    const response = result.text;

    // Simple extraction of objects mentioned (could be enhanced with structured output)
    const objectMatches = response.match(/(?:shows?|contains?|displays?|features?)\s+([^.]+)/gi) || [];
    const objects = objectMatches
      .map((m) => m.replace(/^(shows?|contains?|displays?|features?)\s+/i, "").trim())
      .filter((o) => o.length > 0);

    logger.info("Image analysis completed", {
      hasUrl: !!input.imageUrl,
      hasBase64: !!input.imageBase64,
      latencyMs: Date.now() - startTime,
    });

    return {
      description: response,
      extractedText: input.extractText ? extractTextFromResponse(response) : undefined,
      objects: objects.length > 0 ? objects : undefined,
    };
  } catch (error) {
    logger.error("Image analysis failed", error as Error);
    throw error;
  }
}

/**
 * Extract text section from analysis response
 */
function extractTextFromResponse(response: string): string | undefined {
  // Look for text-related sections
  const textMatch = response.match(
    /(?:text|reads?|says?|written|visible text)[:\s]*["']?([^"'\n]+)["']?/gi
  );
  if (textMatch && textMatch.length > 0) {
    return textMatch.map((m) => m.replace(/^(?:text|reads?|says?|written|visible text)[:\s]*["']?/i, "").replace(/["']$/, "")).join(" ");
  }
  return undefined;
}

/**
 * Image Analysis Tool Definition
 */
export const imageAnalysisTool: ToolDefinition<ImageAnalysisInput, ImageAnalysisResult> = {
  name: "image_analysis",
  description: `Analyze images using vision AI. Use this when:
- The user provides an image URL or base64 encoded image
- You need to understand visual content
- Text extraction from images (OCR) is needed
- Object detection or scene description is required`,
  category: "multimodal",
  inputSchema: ImageAnalysisInputSchema,
  outputSchema: ImageAnalysisResultSchema,
  execute: executeImageAnalysis,
};

/**
 * Get Image Analysis tool for Vercel AI SDK tool calling
 */
export function getImageToolForAI() {
  return {
    image_analysis: {
      description: imageAnalysisTool.description,
      parameters: ImageAnalysisInputSchema,
      execute: async (input: ImageAnalysisInput) => {
        const result = await executeImageAnalysis(input);
        return {
          analysis: result.description,
          extractedText: result.extractedText,
          identifiedObjects: result.objects,
        };
      },
    },
  };
}
