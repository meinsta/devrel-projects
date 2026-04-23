import { GoogleGenerativeAI } from "@google/generative-ai";

const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY!;

let _client: GoogleGenerativeAI | null = null;

function getClient(): GoogleGenerativeAI {
  if (!_client) {
    _client = new GoogleGenerativeAI(GOOGLE_API_KEY);
  }
  return _client;
}

export async function* generateContentStream(prompt: string): AsyncGenerator<string> {
  const client = getClient();
  const model = client.getGenerativeModel({ model: "gemini-2.5-flash" });

  const result = await model.generateContentStream(prompt);

  for await (const chunk of result.stream) {
    const text = chunk.text();
    if (text) {
      yield text;
    }
  }
}

export function buildArticlePrompt(
  topicA: string,
  topicB: string,
  contextA: string,
  contextB: string,
  contextConn: string,
  prefInstructions: string = ""
): string {
  return `You are a Wikipedia-style article writer. Create an engaging article that connects two topics.

**GROUNDING SOURCES (use ONLY these facts):**

About ${topicA}:
${contextA}

About ${topicB}:
${contextB}

Connection context:
${contextConn || "Find conceptual bridges between the topics."}
${prefInstructions}

**TASK:**
Write a wiki-style article (800-1200 words) explaining the fascinating connection between "${topicA}" and "${topicB}".

Requirements:
1. Use ONLY facts from the grounding sources above
2. Find creative but accurate connections
3. Use clear headers and structure
4. Cite sources inline: "According to Wikipedia's [Topic] article..."
5. Make it engaging and educational
${prefInstructions ? "6. IMPORTANT: Apply the user's preferences listed above to customize your writing style" : ""}

Output the article in Markdown format with a creative title.`;
}

