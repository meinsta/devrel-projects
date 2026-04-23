"""
Index the willcb/rare-wiki-pages dataset into Qdrant.
BGE dense embeddings + Qdrant server-side BM25 + payload indexes.
"""

import os
import sys
import time

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

from datasets import load_dataset
from dotenv import load_dotenv
from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

load_dotenv()

COLLECTION = "asteroid_wiki"
BATCH_SIZE = 16
MAX_CHUNK_TOKENS = 512

qdrant = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"), timeout=120)

# Load embedding model
print("Loading embedding model...")
embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")
test_vec = list(embed_model.embed(["test"]))[0]
DENSE_DIM = len(test_vec)
print(f"BGE-small loaded. dim={DENSE_DIM}")

# Load dataset
print("\nLoading dataset...")
ds = load_dataset("willcb/rare-wiki-pages", split="train")
print(f"Loaded {len(ds)} pages")

# Chunk documents
print("\nChunking documents...")


def chunk_text(text, max_words=400, overlap_words=50):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start = end - overlap_words
    return chunks


all_chunks = []
chunk_id = 0
for row in ds:
    title = row["title"]
    page_id = row["id"]
    content = row["content"]

    chunks = chunk_text(content)
    for i, chunk_text_str in enumerate(chunks):
        all_chunks.append({
            "id": chunk_id,
            "title": title,
            "page_id": page_id,
            "section_idx": i,
            "text": chunk_text_str,
        })
        chunk_id += 1

print(f"Created {len(all_chunks)} chunks from {len(ds)} pages")
print(f"Average chunk length: {sum(len(c['text'].split()) for c in all_chunks) / len(all_chunks):.0f} words")

# Create collection (or resume if it exists)
existing_count = 0
try:
    info = qdrant.get_collection(COLLECTION)
    existing_count = info.points_count or 0
    print(f"\nCollection {COLLECTION} exists with {existing_count} points. Resuming.")
except Exception:
    print(f"\nCreating collection {COLLECTION}...")
    qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            "dense": models.VectorParams(size=DENSE_DIM, distance=models.Distance.COSINE),
        },
        sparse_vectors_config={
            "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF),
        },
    )
    qdrant.create_payload_index(COLLECTION, "title", models.PayloadSchemaType.KEYWORD)
    qdrant.create_payload_index(COLLECTION, "page_id", models.PayloadSchemaType.KEYWORD)
    qdrant.create_payload_index(COLLECTION, "section_idx", models.PayloadSchemaType.INTEGER)
    qdrant.create_payload_index(
        COLLECTION, "text",
        models.TextIndexParams(type="text", tokenizer=models.TokenizerType.WORD, min_token_len=2, max_token_len=20),
    )

# Skip already-indexed chunks
if existing_count > 0:
    all_chunks = all_chunks[existing_count:]
    print(f"Skipping {existing_count} already-indexed chunks. {len(all_chunks)} remaining.")

# Index in batches
avg_len = sum(len(c["text"].split()) for c in all_chunks) / len(all_chunks)

print(f"\nIndexing {len(all_chunks)} chunks in batches of {BATCH_SIZE}...")
t0 = time.perf_counter()

for batch_start in range(0, len(all_chunks), BATCH_SIZE):
    batch = all_chunks[batch_start:batch_start + BATCH_SIZE]
    texts = [c["text"] for c in batch]

    # Dense embeddings
    dense_vecs = list(embed_model.embed(texts))

    points = []
    for chunk, dvec in zip(batch, dense_vecs):
        points.append(
            models.PointStruct(
                id=chunk["id"],
                payload={
                    "title": chunk["title"],
                    "page_id": chunk["page_id"],
                    "section_idx": chunk["section_idx"],
                    "text": chunk["text"],
                },
                vector={
                    "dense": dvec.tolist(),
                    "bm25": models.Document(
                        text=chunk["text"],
                        model="Qdrant/bm25",
                        options={"avg_len": avg_len},
                    ),
                },
            )
        )

    for attempt in range(3):
        try:
            qdrant.upsert(collection_name=COLLECTION, points=points)
            break
        except Exception as e:
            if attempt < 2:
                print(f"  Retry {attempt+1}: {e}")
                time.sleep(5)
            else:
                raise

    done = min(batch_start + BATCH_SIZE, len(all_chunks))
    elapsed = time.perf_counter() - t0
    rate = done / elapsed
    eta = (len(all_chunks) - done) / rate if rate > 0 else 0
    print(f"  {done}/{len(all_chunks)} ({rate:.0f} chunks/s, ETA {eta:.0f}s)")

elapsed = time.perf_counter() - t0
print(f"\nDone. Indexed {len(all_chunks)} chunks in {elapsed:.1f}s ({len(all_chunks)/elapsed:.0f} chunks/s)")

# Verify
info_resp = qdrant.get_collection(COLLECTION)
print(f"\nCollection {COLLECTION}:")
print(f"  Points: {info_resp.points_count}")
print(f"  Status: {info_resp.status}")
