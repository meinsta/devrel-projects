import "dotenv/config";
import { ingestDocuments, type DocumentInput } from "../lib/ingestion/pipeline";

/**
 * Seed with SQuAD dataset - real Wikipedia passages with Q&A pairs
 * Uses SQuAD 2.0 dev set (~12k questions, ~500 articles)
 */

const SQUAD_URL =
  "https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v2.0.json";

interface SquadParagraph {
  context: string;
  qas: Array<{
    question: string;
    id: string;
    answers: Array<{ text: string; answer_start: number }>;
    is_impossible: boolean;
  }>;
}

interface SquadArticle {
  title: string;
  paragraphs: SquadParagraph[];
}

interface SquadData {
  version: string;
  data: SquadArticle[];
}

async function downloadSquad(): Promise<SquadData> {
  console.log("Downloading SQuAD 2.0 dev set...");
  const response = await fetch(SQUAD_URL);
  if (!response.ok) {
    throw new Error(`Failed to download SQuAD: ${response.statusText}`);
  }
  const data = (await response.json()) as SquadData;
  console.log(`Downloaded ${data.data.length} articles`);
  return data;
}

function squadToDocuments(
  data: SquadData,
  options: { maxArticles?: number; maxParagraphsPerArticle?: number } = {}
): { documents: DocumentInput[]; questions: QuestionWithContext[] } {
  const { maxArticles = 100, maxParagraphsPerArticle = 5 } = options;

  const documents: DocumentInput[] = [];
  const questions: QuestionWithContext[] = [];

  for (const article of data.data.slice(0, maxArticles)) {
    for (const paragraph of article.paragraphs.slice(
      0,
      maxParagraphsPerArticle
    )) {
      const docId = `squad_${article.title.replace(/\s+/g, "_")}_${documents.length}`;

      documents.push({
        id: docId,
        content: paragraph.context,
        metadata: {
          source: "squad",
          title: article.title,
          tags: ["wikipedia", "squad", "benchmark"],
        },
      });

      // Collect answerable questions
      for (const qa of paragraph.qas) {
        if (!qa.is_impossible && qa.answers.length > 0) {
          questions.push({
            id: qa.id,
            question: qa.question,
            answer: qa.answers[0].text,
            docId,
            articleTitle: article.title,
          });
        }
      }
    }
  }

  return { documents, questions };
}

interface QuestionWithContext {
  id: string;
  question: string;
  answer: string;
  docId: string;
  articleTitle: string;
}

async function main() {
  const args = process.argv.slice(2);
  const maxArticles = parseInt(args[0] || "50", 10);
  const maxParagraphs = parseInt(args[1] || "3", 10);

  console.log(
    `Seeding SQuAD data (max ${maxArticles} articles, ${maxParagraphs} paragraphs each)...`
  );

  // Download dataset
  const squadData = await downloadSquad();

  // Convert to documents
  const { documents, questions } = squadToDocuments(squadData, {
    maxArticles,
    maxParagraphsPerArticle: maxParagraphs,
  });

  console.log(`Prepared ${documents.length} documents`);
  console.log(`Extracted ${questions.length} benchmark questions`);

  // Ingest documents (skip duplicate check for fresh collection)
  console.log("\nIngesting documents...");
  const startTime = Date.now();
  const results = await ingestDocuments(documents, { skipDuplicates: false });
  const duration = (Date.now() - startTime) / 1000;

  const successful = results.filter((r) => r.status === "success");
  const failed = results.filter((r) => r.status === "error");

  console.log(`\nIngested ${successful.length} documents in ${duration.toFixed(1)}s`);
  if (failed.length > 0) {
    console.log(`Failed: ${failed.length}`);
    failed.slice(0, 5).forEach((f) => console.log(`  - ${f.docId}: ${f.error}`));
  }

  const totalChunks = successful.reduce((sum, r) => sum + r.chunkCount, 0);
  const totalTokens = successful.reduce((sum, r) => sum + r.totalTokens, 0);

  console.log(`Total chunks: ${totalChunks}`);
  console.log(`Total tokens: ${totalTokens}`);

  // Save questions for benchmarking
  const fs = await import("fs/promises");
  const questionsFile = "./scripts/benchmark-questions.json";
  const sampleQuestions = questions.slice(0, 200); // Save 200 for benchmarking
  await fs.writeFile(questionsFile, JSON.stringify(sampleQuestions, null, 2));
  console.log(`\nSaved ${sampleQuestions.length} benchmark questions to ${questionsFile}`);

  console.log("\nDone!");
}

main().catch((error) => {
  console.error("Seeding failed:", error);
  process.exit(1);
});
