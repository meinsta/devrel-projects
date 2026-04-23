"""Index BrowseComp+ baseline into Qdrant: dense (bge-small) + BM25 only.

No ColBERT, no A100 needed. ColBERT vectors get added later as an ablation.
Runs on Modal with a T4 GPU (fastembed is fast enough on T4).

Usage:
  modal run scripts/index_browsecomp_baseline.py
  modal run scripts/index_browsecomp_baseline.py --dry-run
  modal run scripts/index_browsecomp_baseline.py --start-offset 500000
"""

import modal

app = modal.App("asteroid-index-browsecomp-baseline")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "datasets>=3.0",
        "qdrant-client>=1.17",
        "fastembed>=0.8.0",
    )
)

COLLECTION = "browsecomp_plus"
UPSERT_BATCH = 64
DENSE_DIM = 384  # bge-small-en-v1.5


@app.function(
    image=image,
    gpu="T4",
    timeout=14400,  # 4 hours
    memory=32768,
    secrets=[modal.Secret.from_name("qdrant")],
)
def index_corpus(start_offset: int = 0, dry_run: bool = False):
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

    print("Loading bge-small-en-v1.5...")
    embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")
    print(f"Dense model loaded (output dim={DENSE_DIM})")

    print("Loading BrowseComp+ corpus...")
    corpus = load_dataset("mjeblicknvidia/browse_comp_plus_512", split="train")
    total = len(corpus)
    print(f"Loaded {total} chunks")
    print(f"Columns: {corpus.column_names}")

    if total > 0:
        sample = corpus[0]
        for k, v in sample.items():
            preview = str(v)[:120] if isinstance(v, str) else str(v)[:120]
            print(f"  {k}: {preview}")

    if dry_run:
        # Count unique docs
        filenames = set()
        for i in range(min(total, 100000)):
            filenames.add(corpus[i]["filename"])
        print(f"\nDry run. {total} chunks, ~{len(filenames)} unique docs (sampled first 100k)")
        return

    # Create collection (only if starting fresh)
    if start_offset == 0:
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
                indexing_threshold=0,  # disable during bulk upload
            ),
        )
        print(f"Created collection {COLLECTION}")

        # Payload indexes for later use
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
        print("Payload indexes created (text FTS, title keyword, doc_id keyword)")

    # Extract title from text frontmatter if present
    title_re = re.compile(r"^---\s*\ntitle:\s*(.+?)\n", re.MULTILINE)

    def extract_title(text: str, filename: str) -> str:
        m = title_re.match(text)
        if m:
            return m.group(1).strip()
        return filename.replace(".txt", "")

    # Index in batches
    point_id = start_offset
    errors = 0

    for batch_start in range(start_offset, total, UPSERT_BATCH):
        batch_end = min(batch_start + UPSERT_BATCH, total)
        batch = corpus[batch_start:batch_end]

        texts = batch["text"]
        filenames = batch["filename"]

        if not texts:
            point_id += UPSERT_BATCH
            continue

        try:
            dense_vecs = list(embed_model.embed(texts))

            points = []
            for j in range(len(texts)):
                text = texts[j] if j < len(texts) else ""
                filename = filenames[j] if j < len(filenames) else f"doc_{point_id}"

                if not text or not text.strip():
                    point_id += 1
                    continue

                title = extract_title(text, filename)
                doc_id = filename.replace(".txt", "")

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
                point_id += 1

            if points:
                qdrant.upsert(collection_name=COLLECTION, points=points)

        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"Error at batch {batch_start}: {e}")
            point_id += len(texts)

        if (batch_start // UPSERT_BATCH) % 500 == 0:
            pct = (point_id / total) * 100
            print(f"  {point_id:>8}/{total} ({pct:.1f}%) | {errors} errors")

    # Re-enable indexing
    qdrant.update_collection(
        collection_name=COLLECTION,
        optimizer_config=models.OptimizersConfigDiff(
            indexing_threshold=20000,
        ),
    )

    print(f"\nIndexing complete. {point_id} points, {errors} errors.")

    # Verify
    info = qdrant.get_collection(COLLECTION)
    print(f"\nCollection: {COLLECTION}")
    print(f"  Points: {info.points_count}")
    print(f"  Vectors: {list(info.config.params.vectors.keys())}")
    print(f"  Sparse: {list(info.config.params.sparse_vectors.keys())}")
    print(f"  Payload indexes: {list(info.payload_schema.keys())}")


@app.local_entrypoint()
def main(dry_run: bool = False, start_offset: int = 0):
    index_corpus.remote(start_offset=start_offset, dry_run=dry_run)
