import "dotenv/config";
import { QdrantClient } from "@qdrant/js-client-rest";
import { CohereClient } from "cohere-ai";

const qdrant = new QdrantClient({
  url: process.env.QDRANT_URL,
  apiKey: process.env.QDRANT_API_KEY,
});

const cohere = new CohereClient({
  token: process.env.COHERE_API_KEY,
});

async function main() {
  // Test embedding
  console.log("Testing Cohere embedding...");
  const response = await cohere.embed({
    texts: ["Hello world"],
    model: "embed-multilingual-v2.0",
    inputType: "search_document",
  });
  const embeddings = response.embeddings as number[][];
  console.log("Embedding dimension:", embeddings[0].length);
  console.log("First 5 values:", embeddings[0].slice(0, 5));

  // Test upsert with dense only
  console.log("\nTesting upsert with dense vector only...");
  try {
    await qdrant.upsert("corpus_chunks", {
      points: [
        {
          id: "550e8400-e29b-41d4-a716-446655440001",
          vector: {
            dense: embeddings[0],
          },
          payload: {
            text: "Hello world",
            doc_id: "test",
          },
        },
      ],
    });
    console.log("Dense-only upsert succeeded!");
  } catch (e) {
    console.error("Dense-only upsert failed:", e);
  }

  // Test upsert with sparse vector
  console.log("\nTesting upsert with sparse vector...");
  try {
    await qdrant.upsert("corpus_chunks", {
      points: [
        {
          id: "550e8400-e29b-41d4-a716-446655440002",
          vector: {
            dense: embeddings[0],
            sparse: {
              indices: [1, 2, 3],
              values: [0.5, 0.3, 0.2],
            },
          },
          payload: {
            text: "Hello world sparse",
            doc_id: "test",
          },
        },
      ],
    });
    console.log("Sparse upsert succeeded!");
  } catch (e) {
    console.error("Sparse upsert failed:", e);
  }
}

main();
