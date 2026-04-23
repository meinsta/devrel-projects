"""Parallel BrowseComp+ indexing: multiple A100 workers with GPU embedding.

Shards the 1.75M chunk corpus across N workers. Each worker embeds its shard
on GPU and upserts to the shared browsecomp_plus collection.

Usage:
  modal run scripts/index_browsecomp_parallel.py --test          # 1 worker, 1000 chunks
  modal run scripts/index_browsecomp_parallel.py                 # 4 workers, full corpus
  modal run scripts/index_browsecomp_parallel.py --workers 8     # 8 workers
"""

import modal

app = modal.App("asteroid-browsecomp-parallel")

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
UPSERT_BATCH = 256


@app.function(
    image=image,
    cpu=4,
    timeout=7200,
    memory=32768,
    secrets=[modal.Secret.from_name("qdrant")],
)
def index_shard(shard_start: int, shard_end: int, total: int, create_collection: bool = False):
    """Index one shard of the corpus."""
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
            print(f"Deleted existing {COLLECTION}")
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
            field_schema=models.TextIndexParams(
                type=models.TextIndexType.TEXT,
            ),
        )
        qdrant.create_payload_index(
            collection_name=COLLECTION,
            field_name="title",
            field_schema=models.KeywordIndexParams(
                type=models.KeywordIndexType.KEYWORD,
            ),
        )
        qdrant.create_payload_index(
            collection_name=COLLECTION,
            field_name="doc_id",
            field_schema=models.KeywordIndexParams(
                type=models.KeywordIndexType.KEYWORD,
            ),
        )
        print(f"Created collection {COLLECTION} with payload indexes")

    # GPU embedding
    print(f"Shard [{shard_start}:{shard_end}] loading model on GPU...")
    embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")
    print("Model loaded on GPU")

    print(f"Loading dataset slice [{shard_start}:{shard_end}]...")
    corpus = load_dataset("mjeblicknvidia/browse_comp_plus_512", split="train")
    shard_end = min(shard_end, len(corpus))
    shard_size = shard_end - shard_start
    print(f"Shard size: {shard_size} chunks")

    title_re = re.compile(r"^---\s*\ntitle:\s*(.+?)\n", re.MULTILINE)

    def extract_title(text: str, filename: str) -> str:
        m = title_re.match(text)
        if m:
            return m.group(1).strip()
        return filename.replace(".txt", "")

    errors = 0
    indexed = 0

    for batch_start in range(shard_start, shard_end, UPSERT_BATCH):
        batch_end = min(batch_start + UPSERT_BATCH, shard_end)
        batch = corpus[batch_start:batch_end]

        texts = batch["text"]
        filenames = batch["filename"]

        if not texts:
            continue

        try:
            dense_vecs = list(embed_model.embed(texts, batch_size=len(texts)))

            points = []
            for j in range(len(texts)):
                text = texts[j]
                filename = filenames[j]

                if not text or not text.strip():
                    continue

                title = extract_title(text, filename)
                doc_id = filename.replace(".txt", "")
                point_id = batch_start + j

                points.append(
                    models.PointStruct(
                        id=point_id,
                        payload={
                            "doc_id": doc_id,
                            "title": title,
                            "text": text,
                        },
                        vector={
                            "dense": dense_vecs[j].tolist(),
                            "bm25": models.Document(
                                text=text,
                                model="Qdrant/bm25",
                            ),
                        },
                    )
                )

            if points:
                qdrant.upsert(collection_name=COLLECTION, points=points)
                indexed += len(points)

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"Error at batch {batch_start}: {e}")

        if (batch_start - shard_start) % (UPSERT_BATCH * 50) == 0:
            pct = ((batch_start - shard_start) / shard_size) * 100 if shard_size else 0
            print(f"  Shard [{shard_start}:{shard_end}] {pct:.1f}% | {indexed} indexed | {errors} errors")

    print(f"Shard [{shard_start}:{shard_end}] done. {indexed} indexed, {errors} errors.")
    return {"shard_start": shard_start, "shard_end": shard_end, "indexed": indexed, "errors": errors}


@app.function(
    image=image,
    timeout=7200,
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
    print(f"\nCollection: {COLLECTION}")
    print(f"  Points: {info.points_count}")
    print(f"  Vectors: {list(info.config.params.vectors.keys())}")
    print(f"  Sparse: {list(info.config.params.sparse_vectors.keys())}")
    print(f"  Payload indexes: {list(info.payload_schema.keys())}")
    return info.points_count


@app.local_entrypoint()
def main(workers: int = 4, test: bool = False):
    if test:
        print("TEST MODE: 1 worker, 1000 chunks")
        result = index_shard.remote(0, 1000, 1000, create_collection=True)
        print(f"Result: {result}")
        final = finalize.remote()
        print(f"Final point count: {final}")
        return

    total = 1_747_677
    shard_size = total // workers
    shards = []
    for i in range(workers):
        start = i * shard_size
        end = start + shard_size if i < workers - 1 else total
        shards.append((start, end))

    print(f"Launching {workers} A100 workers across {total} chunks")
    for i, (s, e) in enumerate(shards):
        print(f"  Worker {i}: [{s}:{e}] ({e-s} chunks)")

    # Worker 0 creates the collection, others just upsert
    futures = []
    for i, (start, end) in enumerate(shards):
        futures.append(index_shard.spawn(start, end, total, create_collection=(i == 0)))

    # Wait for all
    results = [f.get() for f in futures]
    for r in results:
        print(f"  Shard [{r['shard_start']}:{r['shard_end']}]: {r['indexed']} indexed, {r['errors']} errors")

    total_indexed = sum(r["indexed"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    print(f"\nAll shards done. {total_indexed} total indexed, {total_errors} total errors.")

    # Finalize
    final = finalize.remote()
    print(f"Final point count: {final}")
