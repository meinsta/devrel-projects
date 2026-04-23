import { z } from "zod";

const envSchema = z.object({
  // Qdrant
  QDRANT_URL: z.string().url(),
  QDRANT_API_KEY: z.string().min(1),

  // Anthropic
  ANTHROPIC_API_KEY: z.string().min(1),

  // LLM Models
  LLM_CHEAP_MODEL: z.string().default("claude-3-5-haiku-20241022"),
  LLM_STRONG_MODEL: z.string().default("claude-3-5-sonnet-20241022"),

  // Reranker
  RERANKER_PROVIDER: z.enum(["jina", "cohere"]).default("jina"),
  JINA_API_KEY: z.string().optional(),
  COHERE_API_KEY: z.string().min(1),

  // Web Search (Linkup)
  LINKUP_API_KEY: z.string().optional(),

  // Embedding (Cohere embed-multilingual-v2.0 = 768 dims)
  EMBED_SIZE: z.coerce.number().default(768),

  // App
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
}).refine(
  (data) => {
    // Skip reranker validation during build
    if (process.env.NEXT_PHASE === "phase-production-build") return true;
    if (data.RERANKER_PROVIDER === "jina") return !!data.JINA_API_KEY;
    if (data.RERANKER_PROVIDER === "cohere") return !!data.COHERE_API_KEY;
    return true;
  },
  { message: "API key required for selected RERANKER_PROVIDER" }
);

export type Env = z.infer<typeof envSchema>;

let cachedEnv: Env | null = null;

/**
 * Get validated environment variables
 * Throws if required variables are missing
 */
export function getEnv(): Env {
  // Skip validation during build
  if (process.env.NEXT_PHASE === "phase-production-build") {
    return {
      QDRANT_URL: process.env.QDRANT_URL || "http://localhost:6333",
      QDRANT_API_KEY: process.env.QDRANT_API_KEY || "placeholder",
      ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY || "placeholder",
      LLM_CHEAP_MODEL: "claude-3-5-haiku-20241022",
      LLM_STRONG_MODEL: "claude-3-5-sonnet-20241022",
      RERANKER_PROVIDER: "jina",
      JINA_API_KEY: process.env.JINA_API_KEY,
      COHERE_API_KEY: process.env.COHERE_API_KEY || "placeholder",
      LINKUP_API_KEY: process.env.LINKUP_API_KEY,
      EMBED_SIZE: 768,
      NODE_ENV: "production",
    } as Env;
  }

  if (cachedEnv) return cachedEnv;

  const parsed = envSchema.safeParse(process.env);

  if (!parsed.success) {
    console.error("Invalid environment variables:");
    console.error(parsed.error.flatten().fieldErrors);
    throw new Error("Invalid environment variables");
  }

  cachedEnv = parsed.data;
  return cachedEnv;
}

// For backwards compatibility, create a proxy that calls getEnv()
export const env = new Proxy({} as Env, {
  get(_, prop: string) {
    return getEnv()[prop as keyof Env];
  },
});
