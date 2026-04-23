#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from qdrant_client import QdrantClient, models


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / ".data" / "qdrant-memory"
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "codex-memory")
EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)


def _build_client() -> QdrantClient:
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")

    if qdrant_url:
        if not qdrant_api_key:
            raise SystemExit("QDRANT_API_KEY is required when QDRANT_URL is set.")
        return QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    db_path = Path(os.environ.get("QDRANT_LOCAL_PATH", str(DEFAULT_DB_PATH)))
    return QdrantClient(path=str(db_path))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query the Qdrant engineering memory store."
    )
    parser.add_argument("query", help="Natural language query")
    parser.add_argument("--limit", type=int, default=3, help="Number of matches to return")
    args = parser.parse_args()

    client = _build_client()
    try:
        result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=models.Document(text=args.query, model=EMBEDDING_MODEL),
            limit=args.limit,
        )

        for index, point in enumerate(result.points, start=1):
            payload = point.payload or {}
            text = str(payload.get("text", "")).strip()
            preview = text if len(text) <= 220 else f"{text[:217]}..."
            print(f"{index}. {payload.get('title', 'untitled')}  score={point.score:.4f}")
            print(f"   source={payload.get('source_path', 'unknown')}")
            print(f"   {preview}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
