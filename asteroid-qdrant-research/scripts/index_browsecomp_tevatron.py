"""Index Tevatron/browsecomp-plus-corpus into Qdrant with correct docids.

100K docs, chunked at ~512 tokens. Dense (bge-small) + BM25.
Docids match Tevatron/browsecomp-plus gold labels for scoring.

Usage:
  modal run scripts/index_browsecomp_tevatron.py --test
  modal run scripts/index_browsecomp_tevatron.py --workers 4
"""

import modal

app = modal.App("asteroid-browsecomp-tevatron")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "datasets>=3.0",
        "qdrant-client>=1.17",
        "fastembed>=0.8.0",
    )
)

COLLECTION = "browsecomp_plus"
DENSE_DIM = 384
UPSERT_BATCH = 64


@app.function(
    image=image,
    cpu=4,
    timeout=14400,
    memory=32768,
    secrets=[modal.Secret.from_name("qdrant")],
)
def index_shard(shard_start: int, shard_end: int, total_docs: int, create_collection: bool = False):
    """Index one shard of the Tevatron corpus."""
    import os
    import re

    from datasets import load_dataset
    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient, models

    qdrant = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
        timeout=120,
    )

    if create_collection:
        try:
            qdrant.delete_collection(COLLECTION)
        except Exception:
            pass

        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config={
                "dense": models.VectorParams(
                    size=DENSE_DIM,
                    distance=models.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "bm25": models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                ),
            },
            hnsw_config=models.HnswConfigDiff(m=16),
            optimizers_config=models.OptimizersConfigDiff(
                indexing_threshold=0,
            ),
        )

        qdrant.create_payload_index(
            collection_name=COLLECTION,
            field_name="text",
            field_schema=models.TextIndexParams(type=models.TextIndexType.TEXT),
        )
        qdrant.create_payload_index(
            collection_name=COLLECTION,
            field_name="title",
            field_schema=models.KeywordIndexParams(type=models.KeywordIndexType.KEYWORD),
        )
        qdrant.create_payload_index(
            collection_name=COLLECTION,
            field_name="doc_id",
            field_schema=models.KeywordIndexParams(type=models.KeywordIndexType.KEYWORD),
        )
        print(f"Created collection {COLLECTION}")

    print(f"Shard [{shard_start}:{shard_end}] loading model...")
    embed_model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
    print("Model loaded")

    print(f"Loading corpus...")
    corpus = load_dataset("Tevatron/browsecomp-plus-corpus", split="train")
    shard_end = min(shard_end, len(corpus))
    print(f"Shard [{shard_start}:{shard_end}] ({shard_end - shard_start} docs)")

    title_re = re.compile(r"^---\s*\ntitle:\s*(.+?)\n", re.MULTILINE)

    def extract_title(text: str) -> str:
        m = title_re.match(text)
        if m:
            return m.group(1).strip()
        return ""

    errors = 0
    total_chunks = 0
    # Use a global point counter based on shard position
    # Each doc can produce up to ~40 chunks (10K words / 256), use 100 as safe max
    point_id_base = shard_start * 100

    for doc_idx in range(shard_start, shard_end):
        row = corpus[doc_idx]
        doc_id = str(row["docid"])
        text = row.get("text", "")

        if not text or not text.strip():
            continue

        title = extract_title(text)
        # Fixed-size word-level chunks (fair baseline, no semantic enhancement)
        words = text.split()
        if len(words) <= 256:
            chunks = [text] if words else []
        else:
            chunks = []
            for i in range(0, len(words), 220):
                chunks.append(" ".join(words[i:i+256]))

        if not chunks:
            continue

        # Process in sub-batches
        for chunk_batch_start in range(0, len(chunks), UPSERT_BATCH):
            chunk_batch = chunks[chunk_batch_start:chunk_batch_start + UPSERT_BATCH]

            try:
                dense_vecs = list(embed_model.embed(chunk_batch))

                points = []
                for j, (chunk_text_val, dense_vec) in enumerate(zip(chunk_batch, dense_vecs)):
                    pid = point_id_base + chunk_batch_start + j
                    points.append(
                        models.PointStruct(
                            id=pid,
                            payload={
                                "doc_id": doc_id,
                                "title": title,
                                "text": chunk_text_val,
                            },
                            vector={
                                "dense": dense_vec.tolist(),
                                "bm25": models.Document(
                                    text=chunk_text_val,
                                    model="Qdrant/bm25",
                                ),
                            },
                        )
                    )

                if points:
                    qdrant.upsert(collection_name=COLLECTION, points=points)
                    total_chunks += len(points)

            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"Error at doc {doc_idx} chunk_batch {chunk_batch_start}: {e}")

        point_id_base += len(chunks)

        if (doc_idx - shard_start) % 500 == 0 and doc_idx > shard_start:
            pct = ((doc_idx - shard_start) / (shard_end - shard_start)) * 100
            print(f"  Shard [{shard_start}:{shard_end}] {pct:.1f}% | {total_chunks} chunks | {errors} errors")

    print(f"Shard [{shard_start}:{shard_end}] done. {total_chunks} chunks, {errors} errors.")
    return {"shard_start": shard_start, "shard_end": shard_end, "chunks": total_chunks, "errors": errors}


@app.function(
    image=image,
    timeout=3600,
    secrets=[modal.Secret.from_name("qdrant")],
)
def finalize():
    """Re-enable indexing after all shards complete."""
    import os
    from qdrant_client import QdrantClient, models

    qdrant = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
        timeout=120,
    )
    qdrant.update_collection(
        collection_name=COLLECTION,
        optimizer_config=models.OptimizersConfigDiff(
            indexing_threshold=20000,
        ),
    )
    info = qdrant.get_collection(COLLECTION)
    print(f"Collection: {COLLECTION}")
    print(f"  Points: {info.points_count}")
    print(f"  Vectors: {list(info.config.params.vectors.keys())}")
    print(f"  Sparse: {list(info.config.params.sparse_vectors.keys())}")
    return info.points_count


@app.local_entrypoint()
def main(workers: int = 4, test: bool = False):
    total_docs = 100_000

    if test:
        print("TEST MODE: 1 worker, 100 docs")
        result = index_shard.remote(0, 100, total_docs, create_collection=True)
        print(f"Result: {result}")
        final = finalize.remote()
        print(f"Final point count: {final}")
        return

    shard_size = total_docs // workers
    shards = []
    for i in range(workers):
        start = i * shard_size
        end = start + shard_size if i < workers - 1 else total_docs
        shards.append((start, end))

    print(f"Launching {workers} workers across {total_docs} docs")
    for i, (s, e) in enumerate(shards):
        print(f"  Worker {i}: [{s}:{e}] ({e-s} docs)")

    futures = []
    for i, (start, end) in enumerate(shards):
        futures.append(index_shard.spawn(start, end, total_docs, create_collection=(i == 0)))

    results = [f.get() for f in futures]
    for r in results:
        print(f"  Shard [{r['shard_start']}:{r['shard_end']}]: {r['chunks']} chunks, {r['errors']} errors")

    total_chunks = sum(r["chunks"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    print(f"\nAll shards done. {total_chunks} total chunks, {total_errors} total errors.")

    final = finalize.remote()
    print(f"Final point count: {final}")
