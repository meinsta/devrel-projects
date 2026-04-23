"""Index BrowseComp+ into Qdrant using pre-computed Qwen3 embeddings from Tevatron.

Uses document-level embeddings (one vector per doc) from:
  Tevatron/browsecomp-plus-indexes (qwen3-embedding-0.6b, 1024d)

Creates collection: browsecomp_qwen3
"""

import os
import pickle
import sys

from datasets import load_dataset
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
from qdrant_client import QdrantClient, models

load_dotenv()

COLLECTION = "browsecomp_qwen3"
MODEL_DIR = "qwen3-embedding-0.6b"
EMBED_DIM = 1024
NUM_SHARDS = 4


def main():
    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=120,
    )

    # Load corpus texts for payload
    print("Loading corpus texts...", flush=True)
    corpus = load_dataset("Tevatron/browsecomp-plus-corpus", split="train")
    docid_to_text = {}
    for row in corpus:
        docid_to_text[str(row["docid"])] = {
            "text": row["text"][:2000],  # First 2000 chars as snippet
            "title": row.get("url", row.get("title", f"doc_{row['docid']}")),
            "doc_id": str(row["docid"]),
        }
    print(f"  {len(docid_to_text)} docs loaded", flush=True)

    # Create collection
    print(f"Creating collection {COLLECTION}...", flush=True)
    if qdrant.collection_exists(COLLECTION):
        qdrant.delete_collection(COLLECTION)

    qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            "dense": models.VectorParams(
                size=EMBED_DIM,
                distance=models.Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            "bm25": models.SparseVectorParams(
                modifier=models.Modifier.IDF,
            ),
        },
    )

    # Create payload indexes
    qdrant.create_payload_index(COLLECTION, "title", models.PayloadSchemaType.KEYWORD)
    qdrant.create_payload_index(COLLECTION, "doc_id", models.PayloadSchemaType.KEYWORD)
    qdrant.create_payload_index(
        COLLECTION, "text",
        models.TextIndexParams(type="text", tokenizer=models.TokenizerType.WORD, min_token_len=2, max_token_len=20),
    )

    # Download and index each shard
    total_indexed = 0
    for shard_idx in range(1, NUM_SHARDS + 1):
        filename = f"{MODEL_DIR}/corpus.shard{shard_idx}_of_{NUM_SHARDS}.pkl"
        print(f"Downloading shard {shard_idx}/{NUM_SHARDS}...", flush=True)
        path = hf_hub_download("Tevatron/browsecomp-plus-indexes", filename, repo_type="dataset")

        with open(path, "rb") as f:
            embeddings, docids = pickle.load(f)

        print(f"  {len(docids)} docs, {embeddings.shape[1]}d embeddings", flush=True)

        # Batch upsert
        batch_size = 100
        for i in range(0, len(docids), batch_size):
            batch_docids = docids[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]

            points = []
            for j, (docid, vec) in enumerate(zip(batch_docids, batch_embeddings)):
                payload = docid_to_text.get(str(docid), {"text": "", "title": f"doc_{docid}", "doc_id": str(docid)})
                point_id = total_indexed + j
                points.append(models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": vec.tolist(),
                    },
                    payload=payload,
                ))

            qdrant.upsert(collection_name=COLLECTION, points=points)
            total_indexed += len(points)

            if total_indexed % 1000 == 0:
                print(f"  indexed {total_indexed} docs...", flush=True)

    # Now add BM25 vectors via document update
    print(f"\nAdding BM25 sparse vectors...", flush=True)
    offset = None
    bm25_count = 0
    while True:
        points, offset = qdrant.scroll(
            collection_name=COLLECTION,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        if not points:
            break

        updates = []
        for p in points:
            text = (p.payload or {}).get("text", "")
            if text:
                updates.append(models.PointVectors(
                    id=p.id,
                    vector={
                        "bm25": models.Document(text=text, model="Qdrant/bm25"),
                    },
                ))

        if updates:
            qdrant.update_vectors(collection_name=COLLECTION, points=updates)
            bm25_count += len(updates)

        if bm25_count % 1000 == 0:
            print(f"  BM25: {bm25_count} docs...", flush=True)

        if offset is None:
            break

    print(f"\nDone! Collection {COLLECTION}: {total_indexed} docs indexed ({EMBED_DIM}d Qwen3 + BM25)", flush=True)

    # Verify
    info = qdrant.get_collection(COLLECTION)
    print(f"  Points: {info.points_count}", flush=True)
    print(f"  Vectors: {info.vectors_count}", flush=True)


if __name__ == "__main__":
    main()
