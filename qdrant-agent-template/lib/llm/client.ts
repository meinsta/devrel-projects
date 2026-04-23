import { anthropic } from "@ai-sdk/anthropic";
import { generateText, generateObject, streamText } from "ai";
import { z } from "zod";
import { env } from "@/lib/shared/env";
import { logger } from "@/lib/shared/logger";
import { LLMError } from "@/lib/shared/errors";

/**
 * Two-tier LLM configuration
 * - cheap: Fast/cheap model for orchestration (routing, planning, critique)
 * - strong: Powerful model for final answer generation
 */
export const models = {
  cheap: anthropic(env.LLM_CHEAP_MODEL),
  strong: anthropic(env.LLM_STRONG_MODEL),
};

export type ModelTier = keyof typeof models;

/**
 * Generate text with the specified model tier
 */
export async function generate(options: {
  tier: ModelTier;
  system: string;
  prompt: string;
  maxTokens?: number;
}): Promise<string> {
  const { tier, system, prompt, maxTokens = 2048 } = options;

  logger.debug("LLM generate", { tier, promptLength: prompt.length });

  try {
    const result = await generateText({
      model: models[tier],
      system,
      prompt,
      maxTokens,
    });

    return result.text;
  } catch (error) {
    logger.error("LLM generation failed", error as Error, { tier });
    throw new LLMError(`LLM generation failed: ${(error as Error).message}`);
  }
}

/**
 * Generate structured JSON output with the specified model tier
 */
export async function generateJSON<T>(options: {
  tier: ModelTier;
  system: string;
  prompt: string;
  schema: z.ZodType<T>;
  maxTokens?: number;
}): Promise<T> {
  const { tier, system, prompt, schema, maxTokens = 2048 } = options;

  logger.debug("LLM generateJSON", { tier, promptLength: prompt.length });

  try {
    const result = await generateObject({
      model: models[tier],
      system,
      prompt,
      schema,
      maxTokens,
    });

    return result.object;
  } catch (error) {
    logger.error("LLM JSON generation failed", error as Error, { tier });
    throw new LLMError(`LLM JSON generation failed: ${(error as Error).message}`);
  }
}

/**
 * Stream text generation
 */
export async function* generateStream(options: {
  tier: ModelTier;
  system: string;
  prompt: string;
  maxTokens?: number;
}): AsyncGenerator<string> {
  const { tier, system, prompt, maxTokens = 4096 } = options;

  logger.debug("LLM stream", { tier, promptLength: prompt.length });

  try {
    const result = streamText({
      model: models[tier],
      system,
      prompt,
      maxTokens,
    });

    for await (const chunk of result.textStream) {
      yield chunk;
    }
  } catch (error) {
    logger.error("LLM streaming failed", error as Error, { tier });
    throw new LLMError(`LLM streaming failed: ${(error as Error).message}`);
  }
}

/**
 * Helper to create a streaming response
 */
export function createStreamingResponse(
  generator: AsyncGenerator<string>,
  headers?: Record<string, string>
): Response {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      try {
        for await (const chunk of generator) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ text: chunk })}\n\n`));
        }
        controller.enqueue(encoder.encode("data: [DONE]\n\n"));
        controller.close();
      } catch (error) {
        controller.error(error);
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      ...headers,
    },
  });
}
