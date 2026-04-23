"""Add ColBERT multivectors to existing browsecomp_plus collection.

Runs after baseline indexing (dense + BM25) completes. Reads existing points,
computes ColBERT embeddings, and upserts the new vector field. Does not touch
existing dense/BM25 vectors or payloads.

Usage:
  modal run scripts/upsert_browsecomp_colbert.py --test          # 1000 points
  modal run scripts/upsert_browsecomp_colbert.py                 # 4 workers, full
  modal run scripts/upsert_browsecomp_colbert.py --workers 8
"""

import modal

app = modal.App("asteroid-browsecomp-colbert")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "qdrant-client>=1.17",
        "fastembed>=0.8.0",
    )
)

COLLECTION = "browsecomp_plus"
COLBERT_DIM = 128
BATCH_SIZE = 32  # ColBERT is heavier per token, smaller batches


@app.function(
    image=image,
    cpu=4,
    timeout=7200,
    memory=32768,
    secrets=[modal.Secret.from_name("qdrant")],
)
def upsert_colbert_shard(shard_start: int, shard_end: int, total: int, add_vector_config: bool = False):
    """Read existing points, compute ColBERT, upsert vectors."""
    import os

    from fastembed import LateInteractionTextEmbedding
    from qdrant_client import QdrantClient, models

    qdrant = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
        timeout=120,
    )

    # Add ColBERT vector config to collection (only first worker)
    if add_vector_config:
        try:
            qdrant.update_collection(
                collection_name=COLLECTION,
                vectors_config={
                    "colbert": models.VectorParams(
                        size=COLBERT_DIM,
                        distance=models.Distance.COSINE,
                        multivector_config=models.MultiVectorConfig(
                            comparator=models.MultiVectorComparator.MAX_SIM,
                        ),
                    ),
                },
            )
            print(f"Added ColBERT vector config to {COLLECTION}")
        except Exception as e:
            print(f"ColBERT config already exists or error: {e}")

    print(f"Shard [{shard_start}:{shard_end}] loading ColBERT model...")
    colbert_model = LateInteractionTextEmbedding("colbert-ir/colbertv2.0")
    print("ColBERT model loaded")

    shard_size = shard_end - shard_start
    errors = 0
    updated = 0

    for batch_start in range(shard_start, shard_end, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, shard_end)
        point_ids = list(range(batch_start, batch_end))

        try:
            # Fetch existing points (text payload only)
            points = qdrant.retrieve(
                collection_name=COLLECTION,
                ids=point_ids,
                with_payload=["text"],
                with_vectors=False,
            )

            if not points:
                continue

            texts = []
            valid_ids = []
            for p in points:
                text = (p.payload or {}).get("text", "")
                if text:
                    texts.append(text[:2000])  # cap for ColBERT token limit
                    valid_ids.append(p.id)

            if not texts:
                continue

            # Compute ColBERT embeddings
            colbert_vecs = list(colbert_model.embed(texts))

            # Upsert only the new vector
            update_points = []
            for pid, cvec in zip(valid_ids, colbert_vecs):
                update_points.append(
                    models.PointVectors(
                        id=pid,
                        vector={"colbert": cvec.tolist()},
                    )
                )

            if update_points:
                qdrant.update_vectors(
                    collection_name=COLLECTION,
                    points=update_points,
                )
                updated += len(update_points)

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"Error at batch {batch_start}: {e}")

        if (batch_start - shard_start) % (BATCH_SIZE * 100) == 0:
            pct = ((batch_start - shard_start) / shard_size) * 100 if shard_size else 0
            print(f"  Shard [{shard_start}:{shard_end}] {pct:.1f}% | {updated} updated | {errors} errors")

    print(f"Shard [{shard_start}:{shard_end}] done. {updated} updated, {errors} errors.")
    return {"shard_start": shard_start, "shard_end": shard_end, "updated": updated, "errors": errors}


@app.local_entrypoint()
def main(workers: int = 4, test: bool = False):
    # Get total from a remote function instead of local client
    total = 2_053_644  # Known from completed indexing run
    print(f"Collection {COLLECTION}: {total} points")

    if test:
        test_end = min(1000, total)
        print(f"TEST MODE: 1 worker, {test_end} points")
        result = upsert_colbert_shard.remote(0, test_end, total, add_vector_config=True)
        print(f"Result: {result}")
        return

    shard_size = total // workers
    shards = []
    for i in range(workers):
        start = i * shard_size
        end = start + shard_size if i < workers - 1 else total
        shards.append((start, end))

    print(f"Launching {workers} workers for ColBERT upsert across {total} points")
    for i, (s, e) in enumerate(shards):
        print(f"  Worker {i}: [{s}:{e}] ({e-s} points)")

    futures = []
    for i, (start, end) in enumerate(shards):
        futures.append(upsert_colbert_shard.spawn(start, end, total, add_vector_config=(i == 0)))

    results = [f.get() for f in futures]
    for r in results:
        print(f"  Shard [{r['shard_start']}:{r['shard_end']}]: {r['updated']} updated, {r['errors']} errors")

    total_updated = sum(r["updated"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    print(f"\nAll shards done. {total_updated} total updated, {total_errors} total errors.")
