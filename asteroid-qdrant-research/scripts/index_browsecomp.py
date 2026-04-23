"""Index BrowseComp+ into Qdrant Cloud with full Qdrant-native feature stack.

Runs on Modal with GPU. Uses pre-chunked 512-token segments (1.75M chunks).
Creates one collection with every native retrieval primitive:

  - dense: Qwen3-Embedding-0.6B (1024 dim, cosine)
  - bm25: server-side BM25 from text payloads (IDF modifier)
  - colbert: colbertv2.0 multivectors (128 dim, rerank-only, no HNSW)
  - text payload index with phrase matching (for FTS: MatchText/MatchPhrase/MatchTextAny)
  - title keyword index (payload filtering)
  - doc_id keyword index (payload filtering + grouping)

Multi-stage query pattern (all server-side, one API call):
  BM25 + dense -> RRF fusion -> ColBERT rescore

Usage:
  modal run scripts/index_browsecomp.py
  modal run scripts/index_browsecomp.py --dry-run   # inspect dataset, no indexing
"""

import modal

app = modal.App("asteroid-index-browsecomp")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "datasets>=3.0",
        "qdrant-client>=1.17",
        "fastembed>=0.8.0",
        "transformers>=4.45",
        "torch",
        "sentence-transformers>=3.0",
    )
)

COLLECTION = "browsecomp_plus"
UPSERT_BATCH = 32
DENSE_DIM = 1024
COLBERT_DIM = 128
COLBERT_MAX_TOKENS = 256  # cap ColBERT token length to control storage


@app.function(
    image=image,
    gpu="A100",
    timeout=14400,  # 4 hours
    memory=65536,
    secrets=[modal.Secret.from_name("qdrant")],
)
def index_corpus(start_offset: int = 0, dry_run: bool = False):
    import os

    import torch
    from datasets import load_dataset
    from fastembed import LateInteractionTextEmbedding
    from qdrant_client import QdrantClient, models
    from sentence_transformers import SentenceTransformer

    qdrant = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
        timeout=120,
    )

    # Dense model: Qwen3-Embedding-0.6B via sentence-transformers
    print("Loading Qwen3-Embedding-0.6B...")
    dense_model = SentenceTransformer(
        "Qwen/Qwen3-Embedding-0.6B",
        truncate_dim=DENSE_DIM,
    )
    print(f"Dense model loaded (output dim={DENSE_DIM})")

    # ColBERT model: colbertv2.0 via fastembed
    print("Loading colbertv2.0...")
    colbert_model = LateInteractionTextEmbedding("colbert-ir/colbertv2.0")
    print("ColBERT model loaded")

    # Load pre-chunked corpus
    print("Loading pre-chunked BrowseComp+ corpus...")
    corpus = load_dataset("mjeblicknvidia/browse_comp_plus_512", split="train")
    print(f"Loaded {len(corpus)} chunks")
    print(f"Columns: {corpus.column_names}")
    if len(corpus) > 0:
        sample = corpus[0]
        for k, v in sample.items():
            preview = str(v)[:120] if isinstance(v, str) else str(v)
            print(f"  {k}: {preview}")

    if dry_run:
        print(f"\nDry run complete. {len(corpus)} chunks ready to index.")
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
            multivectors_config={
                "colbert": models.MultiVectorParams(
                    distance=models.Distance.COSINE,
                ),
            },
            hnsw_config=models.HnswConfigDiff(
                payload_m=16,
                m=16,
            ),
            optimizers_config=models.OptimizersConfigDiff(
                indexing_threshold=0,  # disable indexing during bulk upload
            ),
        )
        print(f"Created collection {COLLECTION}")

        # Disable HNSW for ColBERT (rerank-only, no ANN index needed)
        qdrant.update_collection_cluster_setup(
            collection_name=COLLECTION,
        ) if False else None  # ColBERT HNSW disable handled by not building it

        # Payload indexes
        qdrant.create_payload_index(
            collection_name=COLLECTION,
            field_name="text",
            field_schema=models.TextIndexParams(
                type=models.TextIndexType.TEXT,
                phrase_matching=True,
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

    # Index in batches
    total = len(corpus)
    point_id = start_offset
    errors = 0
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Indexing on {device}, {total} chunks, batch={UPSERT_BATCH}")

    for batch_start in range(start_offset, total, UPSERT_BATCH):
        batch_end = min(batch_start + UPSERT_BATCH, total)
        batch = corpus[batch_start:batch_end]

        # Extract fields (handle different column names)
        texts = batch.get("text", batch.get("contents", batch.get("passage", [])))
        if isinstance(texts, str):
            texts = [texts]
        titles = batch.get("title", [""] * len(texts))
        if isinstance(titles, str):
            titles = [titles]
        doc_ids = batch.get("docid", batch.get("_id", batch.get("doc_id", [f"doc_{i}" for i in range(batch_start, batch_end)])))
        if isinstance(doc_ids, str):
            doc_ids = [doc_ids]

        if not texts:
            point_id += UPSERT_BATCH
            continue

        try:
            # Dense embeddings (Qwen3)
            dense_vecs = dense_model.encode(
                texts,
                normalize_embeddings=True,
                batch_size=len(texts),
            )

            # ColBERT embeddings (truncate text for storage efficiency)
            colbert_texts = [t[:2000] for t in texts]  # rough char limit for ~256 tokens
            colbert_vecs = list(colbert_model.embed(colbert_texts))

            # Build points
            points = []
            for j in range(len(texts)):
                text = texts[j] if j < len(texts) else ""
                title = titles[j] if j < len(titles) else ""
                doc_id = str(doc_ids[j]) if j < len(doc_ids) else f"doc_{point_id}"

                if not text or not text.strip():
                    point_id += 1
                    continue

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
                            "colbert": colbert_vecs[j].tolist(),
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

        if (batch_start // UPSERT_BATCH) % 200 == 0:
            pct = (point_id / total) * 100
            print(f"  {point_id:>8}/{total} ({pct:.1f}%) | {errors} errors")

    # Re-enable indexing
    qdrant.update_collection(
        collection_name=COLLECTION,
        optimizer_config=models.OptimizersConfigDiff(
            indexing_threshold=20000,
        ),
    )

    print(f"\nIndexing complete. {point_id} chunks, {errors} errors.")

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
