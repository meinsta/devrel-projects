import "dotenv/config";
import { createCollections, deleteAllCollections } from "../lib/retrieval/collections";
import { checkQdrantHealth } from "../lib/retrieval/client";

async function main() {
  const args = process.argv.slice(2);
  const reset = args.includes("--reset");

  console.log("Checking Qdrant connection...");
  
  const healthy = await checkQdrantHealth();
  if (!healthy) {
    console.error("Failed to connect to Qdrant. Check QDRANT_URL and QDRANT_API_KEY.");
    process.exit(1);
  }
  
  console.log("Connected to Qdrant.");

  if (reset) {
    console.log("Resetting collections (--reset flag)...");
    await deleteAllCollections();
    console.log("Collections deleted.");
  }

  console.log("Creating collections...");
  await createCollections();
  console.log("Setup complete!");
}

main().catch((error) => {
  console.error("Setup failed:", error);
  process.exit(1);
});
