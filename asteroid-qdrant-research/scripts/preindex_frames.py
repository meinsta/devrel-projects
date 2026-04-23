"""Pre-index all FRAMES Wikipedia articles into Qdrant with semantic chunking.

Run this once before training. Each FRAMES question gets its own collection
with semantically chunked Wikipedia articles.
"""

import hashlib
import json
import os
import sys
import time

import httpx
from chonkie import SemanticChunker
from chonkie.embeddings import SentenceTransformerEmbeddings
from datasets import load_dataset
from dotenv import load_dotenv
from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

sys.stdout.reconfigure(line_buffering=True)
load_dotenv()

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
CHUNK_SIZE = 512


def fetch_wikipedia(url: str) -> tuple[str, str]:
    try:
        api_title = url.split("/wiki/")[-1]
        api_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={api_title}&prop=extracts&explaintext=1&format=json"
        resp = httpx.get(api_url, timeout=15, follow_redirects=True, headers={"User-Agent": "Asteroid/1.0 (research; contact@asteroid.dev)"})
        if resp.status_code == 200:
            pages = resp.json().get("query", {}).get("pages", {})
            for page in pages.values():
                text = page.get("extract", "")
                if text:
                    return page.get("title", api_title), text
        title = url.rstrip("/").split("/")[-1].replace("_", " ")
        return title, ""
    except Exception as e:
        title = url.rstrip("/").split("/")[-1].replace("_", " ")
        return title, ""


def main():
    qdrant = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"), timeout=60)
    embed_model = TextEmbedding(EMBED_MODEL)
    # Use same model for chunking and embedding so semantic boundaries align with search
    chunker = SemanticChunker(
        embedding_model=SentenceTransformerEmbeddings(EMBED_MODEL),
        chunk_size=CHUNK_SIZE,
    )

    ds = load_dataset("google/frames-benchmark", split="test")
    print(f"FRAMES: {len(ds)} questions")

    wiki_cache = {}
    total_chunks = 0
    total_articles = 0
    errors = 0

    for i, row in enumerate(ds):
        prompt = row.get("Prompt", "")
        collection_id = f"fr_{hashlib.md5(prompt.encode()).hexdigest()[:10]}"

        # Collect URLs
        wiki_urls = []
        wiki_links = row.get("wiki_links")
        if wiki_links:
            if isinstance(wiki_links, str):
                import ast
                try:
                    wiki_urls = ast.literal_eval(wiki_links)
                except Exception:
                    try:
                        wiki_urls = json.loads(wiki_links)
                    except Exception:
                        wiki_urls = [u.strip() for u in wiki_links.split(",") if u.strip()]
            elif isinstance(wiki_links, list):
                wiki_urls = wiki_links

        for j in range(1, 12):
            key = f"wikipedia_link_{j}" if j < 11 else "wikipedia_link_11+"
            val = row.get(key)
            if val and isinstance(val, str) and "wikipedia" in val:
                wiki_urls.append(val)

        wiki_urls = list(set(u for u in wiki_urls if u and "wikipedia" in str(u)))

        if not wiki_urls:
            continue

        # Check if collection exists
        try:
            info = qdrant.get_collection(collection_id)
            if info.points_count and info.points_count > 0:
                print(f"[{i+1}/{len(ds)}] SKIP {collection_id} ({info.points_count} points)")
                continue
        except Exception:
            pass

        # Fetch articles and index
        all_chunks = []
        for url in wiki_urls[:10]:
            if url in wiki_cache:
                title, text = wiki_cache[url]
            else:
                title, text = fetch_wikipedia(url)
                wiki_cache[url] = (title, text)
                total_articles += 1
                time.sleep(0.1)  # rate limit

            if not text:
                continue

            # Semantic chunking
            try:
                chunks = chunker(text)
                for chunk in chunks:
                    all_chunks.append({"title": title, "text": chunk.text})
            except Exception:
                # Fallback to simple chunking
                words = text.split()
                for k in range(0, len(words), 250):
                    chunk_text = " ".join(words[k:k + 300])
                    all_chunks.append({"title": title, "text": chunk_text})

        if not all_chunks:
            continue

        # Create collection and index
        try:
            try:
                qdrant.delete_collection(collection_id)
            except Exception:
                pass

            qdrant.create_collection(
                collection_name=collection_id,
                vectors_config={"dense": models.VectorParams(size=384, distance=models.Distance.COSINE)},
                sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
            )

            avg_len = sum(len(c["text"].split()) for c in all_chunks) / len(all_chunks)
            texts = [c["text"] for c in all_chunks]
            dense_vecs = list(embed_model.embed(texts))

            points = []
            for idx, (chunk, dvec) in enumerate(zip(all_chunks, dense_vecs)):
                points.append(models.PointStruct(
                    id=idx,
                    payload={"title": chunk["title"], "text": chunk["text"]},
                    vector={
                        "dense": dvec.tolist(),
                        "bm25": models.Document(text=chunk["text"], model="Qdrant/bm25", options={"avg_len": avg_len}),
                    },
                ))

            # Batch upsert
            for batch_start in range(0, len(points), 32):
                batch = points[batch_start:batch_start + 32]
                qdrant.upsert(collection_name=collection_id, points=batch)

            total_chunks += len(all_chunks)
            print(f"[{i+1}/{len(ds)}] {collection_id}: {len(all_chunks)} chunks from {len(wiki_urls)} articles")

        except Exception as e:
            errors += 1
            print(f"[{i+1}/{len(ds)}] ERROR: {e}")

    print(f"\nDone. {total_articles} articles fetched, {total_chunks} chunks indexed, {errors} errors.")


if __name__ == "__main__":
    main()
