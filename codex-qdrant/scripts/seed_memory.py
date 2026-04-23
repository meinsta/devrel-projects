#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from qdrant_client import QdrantClient, models


ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT / "memory"
DEFAULT_DB_PATH = ROOT / ".data" / "qdrant-memory"
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "codex-memory")
EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
MAX_CHUNK_CHARS = int(os.environ.get("MAX_CHUNK_CHARS", "900"))


@dataclass
class Chunk:
    source_path: str
    title: str
    chunk_index: int
    text: str


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _chunk_markdown(path: Path) -> list[Chunk]:
    raw_text = path.read_text(encoding="utf-8")
    parts = [_normalize_whitespace(part) for part in re.split(r"\n\s*\n", raw_text)]
    parts = [part for part in parts if part]
    title = path.stem.replace("-", " ")

    chunks: list[Chunk] = []
    current: list[str] = []
    current_size = 0

    for part in parts:
        projected_size = current_size + len(part) + 2
        if current and projected_size > MAX_CHUNK_CHARS:
            chunks.append(
                Chunk(
                    source_path=str(path.relative_to(ROOT)),
                    title=title,
                    chunk_index=len(chunks),
                    text="\n\n".join(current),
                )
            )
            current = [part]
            current_size = len(part)
            continue

        current.append(part)
        current_size = projected_size

    if current:
        chunks.append(
            Chunk(
                source_path=str(path.relative_to(ROOT)),
                title=title,
                chunk_index=len(chunks),
                text="\n\n".join(current),
            )
        )

    return chunks


def _chunk_id(chunk: Chunk) -> str:
    digest = hashlib.sha256(
        f"{chunk.source_path}:{chunk.chunk_index}:{chunk.text}".encode("utf-8")
    ).hexdigest()
    return digest[:32]


def _load_chunks() -> list[Chunk]:
    files = sorted(MEMORY_DIR.glob("*.md"))
    if not files:
        raise SystemExit(f"No markdown files found in {MEMORY_DIR}")

    chunks: list[Chunk] = []
    for path in files:
        chunks.extend(_chunk_markdown(path))
    return chunks


def _build_client() -> tuple[QdrantClient, str]:
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")

    if qdrant_url:
        if not qdrant_api_key:
            raise SystemExit("QDRANT_API_KEY is required when QDRANT_URL is set.")
        return (
            QdrantClient(url=qdrant_url, api_key=qdrant_api_key),
            f"cloud cluster at {qdrant_url}",
        )

    db_path = Path(os.environ.get("QDRANT_LOCAL_PATH", str(DEFAULT_DB_PATH)))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(db_path)), str(db_path)


def main() -> None:
    client, target_label = _build_client()
    try:
        chunks = _load_chunks()
        documents = [
            models.Document(text=chunk.text, model=EMBEDDING_MODEL) for chunk in chunks
        ]
        payloads = [
            {
                "source_path": chunk.source_path,
                "title": chunk.title,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "topic": "engineering-memory",
            }
            for chunk in chunks
        ]
        ids = [_chunk_id(chunk) for chunk in chunks]

        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=client.get_embedding_size(EMBEDDING_MODEL),
                distance=models.Distance.COSINE,
            ),
        )
        client.upload_collection(
            collection_name=COLLECTION_NAME,
            vectors=documents,
            ids=ids,
            payload=payloads,
        )

        print(
            f"Seeded {len(chunks)} chunks from {len(set(chunk.source_path for chunk in chunks))} files "
            f"into '{COLLECTION_NAME}' at {target_label}"
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
