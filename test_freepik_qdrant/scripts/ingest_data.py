#!/usr/bin/env python3
"""
Stream the crossingminds/shopping-queries-image-dataset, embed images from URLs,
and upsert them into a Qdrant collection.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, Iterator, List

import requests
from datasets import IterableDataset, load_dataset  # type: ignore
from dotenv import load_dotenv
from fastembed import ImageEmbedding
from PIL import Image  # type: ignore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams


DATASET_REPO = "crossingminds/shopping-queries-image-dataset"
DATASET_SPLIT = "train"
DEFAULT_COLLECTION = "shopping-queries-images"
DEFAULT_LIMIT = 100
DEFAULT_BATCH_SIZE = 32  # Increased from 16 for better throughput
DEFAULT_MODEL = "Qdrant/clip-ViT-B-32-vision"
DEFAULT_DOWNLOAD_WORKERS = 10
DEFAULT_DOWNLOAD_TIMEOUT = 10


def require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def batched(iterable: Iterable[dict], size: int) -> Iterator[List[dict]]:
    batch: List[dict] = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def normalize_image(image: Image.Image) -> Image.Image:
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def ensure_collection(client: QdrantClient, name: str, vector_size: int) -> None:
    collections = {c.name for c in client.get_collections().collections}
    if name in collections:
        return
    logging.info("Creating collection '%s' with vector size %d", name, vector_size)
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def iter_samples(limit: int) -> Iterable[dict]:
    dataset: IterableDataset = load_dataset(
        DATASET_REPO,
        name="product_image_urls",  # This config contains product_id and image_url
        split=DATASET_SPLIT,
        streaming=True,
    )
    return itertools.islice(dataset, limit)


def download_image(url: str, timeout: int = 10) -> Image.Image | None:
    """
    Download an image from a URL and return as PIL Image.
    
    FastEmbed doesn't accept URLs directly - it needs file paths or PIL Images.
    We download to memory (stream=True) and return a PIL Image object,
    which FastEmbed can process directly without saving to disk.
    """
    if not url:
        return None
    try:
        # Use session for connection pooling
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        return Image.open(response.raw)
    except Exception as exc:  # noqa: BLE001
        logging.debug("Failed to download image from %s: %s", url[:80], exc)
        return None


def download_images_parallel(
    urls: List[str],
    max_workers: int = 10,
    timeout: int = 10,
) -> List[Image.Image | None]:
    """
    Download multiple images in parallel using ThreadPoolExecutor.
    Returns a list of PIL Images or None for failed downloads.
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(download_image, url, timeout): url for url in urls}
        results = [None] * len(urls)
        url_to_index = {url: i for i, url in enumerate(urls)}
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                img = future.result()
                results[url_to_index[url]] = img
            except Exception as exc:
                logging.debug("Failed to download %s: %s", url[:80], exc)
                results[url_to_index[url]] = None
        
        return results


def product_id_to_int(product_id: str) -> int:
    """Convert product_id string to a consistent integer ID."""
    return int(hashlib.md5(product_id.encode()).hexdigest()[:8], 16)


def generate_points(
    model: ImageEmbedding,
    samples: Iterable[dict],
    embedding_batch_size: int,
    total_items: int | None = None,
    download_workers: int = 10,
    download_timeout: int = 10,
) -> Iterator[PointStruct]:
    """
    Generator that yields PointStruct objects as we process samples.
    This allows streaming ingestion without loading everything into memory.
    
    Uses parallel image downloads to speed up processing.
    """
    from tqdm import tqdm
    
    batch: List[dict] = []
    processed = 0
    progress = tqdm(total=total_items, desc="Processing images", unit="images", leave=True) if total_items else None
    
    for sample in samples:
        batch.append(sample)
        if len(batch) < embedding_batch_size:
            continue
        
        # Process batch - download images in parallel
        valid_samples: List[dict] = []
        image_urls: List[str] = []
        for item in batch:
            image_url = item.get("image_url")
            if image_url:
                valid_samples.append(item)
                image_urls.append(image_url)
        
        if image_urls:
            # Download images in parallel
            downloaded_images = download_images_parallel(
                image_urls,
                max_workers=download_workers,
                timeout=download_timeout,
            )
            
            # Filter out None (failed downloads) and normalize
            images: List[Image.Image] = []
            successful_samples: List[dict] = []
            for img, sample_item in zip(downloaded_images, valid_samples):
                if img:
                    images.append(normalize_image(img))
                    successful_samples.append(sample_item)
            
            if images:
                # Generate embeddings
                embeddings = list(model.embed(images, batch_size=embedding_batch_size))
                # Yield points
                for sample_item, emb in zip(successful_samples, embeddings):
                    product_id = sample_item.get("product_id", "")
                    processed += 1
                    if progress:
                        progress.update(1)
                        progress.set_postfix(processed=processed)
                    yield PointStruct(
                        id=product_id_to_int(product_id),
                        vector=emb.tolist(),
                        payload={
                            "product_id": product_id,
                            "image_url": sample_item.get("image_url"),
                        },
                    )
        
        batch = []
    
    # Process remaining items
    if batch:
        valid_samples = []
        image_urls = []
        for item in batch:
            image_url = item.get("image_url")
            if image_url:
                valid_samples.append(item)
                image_urls.append(image_url)
        
        if image_urls:
            # Download images in parallel
            downloaded_images = download_images_parallel(
                image_urls,
                max_workers=download_workers,
                timeout=download_timeout,
            )
            
            # Filter out None (failed downloads) and normalize
            images = []
            successful_samples = []
            for img, sample_item in zip(downloaded_images, valid_samples):
                if img:
                    images.append(normalize_image(img))
                    successful_samples.append(sample_item)
            
            if images:
                embeddings = list(model.embed(images, batch_size=embedding_batch_size))
                for sample_item, emb in zip(successful_samples, embeddings):
                    product_id = sample_item.get("product_id", "")
                    processed += 1
                    if progress:
                        progress.update(1)
                        progress.set_postfix(processed=processed)
                    yield PointStruct(
                        id=product_id_to_int(product_id),
                        vector=emb.tolist(),
                        payload={
                            "product_id": product_id,
                            "image_url": sample_item.get("image_url"),
                        },
                    )
    
    if progress:
        progress.close()


def ingest_with_upload_points(
    client: QdrantClient,
    collection_name: str,
    model: ImageEmbedding,
    samples: Iterable[dict],
    embedding_batch_size: int,
    upload_batch_size: int = 256,
    parallel: int = 4,
    vector_size: int | None = None,
    total_items: int | None = None,
    download_workers: int = 10,
    download_timeout: int = 10,
) -> None:
    """
    Use upload_points for efficient large-scale ingestion.
    This streams data from an iterator, making it memory-efficient.
    
    According to Qdrant best practices:
    - < 100k points: batched upsert is fine
    - 100k-1M points: upload_points is recommended (what we use here)
    - > 1M points: upload_collection (streaming) is ideal for raw vectors
    """
    # Determine vector size if not provided
    if vector_size is None:
        # Convert to list to peek at first sample without consuming iterator
        samples_list = list(samples)
        if not samples_list:
            raise ValueError("No samples to process")
        
        # Process first sample to get vector size
        first_sample = samples_list[0]
        img = download_image(first_sample.get("image_url", ""))
        if not img:
            raise ValueError("Failed to get sample image")
        test_emb = list(model.embed([normalize_image(img)], batch_size=1))[0]
        vector_size = len(test_emb)
        
        # Use the full list as samples
        samples = iter(samples_list)
    
    # Ensure collection exists
    ensure_collection(client, collection_name, vector_size)
    
    # Generate points iterator (streams from samples, memory-efficient)
    points_generator = generate_points(
        model,
        samples,
        embedding_batch_size,
        total_items=total_items,
        download_workers=download_workers,
        download_timeout=download_timeout,
    )
    
    # Use upload_points for efficient streaming upload with PointStruct objects
    # This handles batching, retries, and parallelism automatically
    client.upload_points(
        collection_name=collection_name,
        points=points_generator,
        batch_size=upload_batch_size,
        parallel=parallel,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream, embed, and ingest shopping-queries images into Qdrant."
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION),
        help="Target Qdrant collection name",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Number of samples to ingest (may be less if some images fail to download)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Embedding batch size (for FastEmbed)",
    )
    parser.add_argument(
        "--upload-batch-size",
        type=int,
        default=256,
        help="Qdrant upload batch size (default: 256)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=4,
        help="Number of parallel upload threads (default: 4)",
    )
    parser.add_argument(
        "--download-workers",
        type=int,
        default=10,
        help="Number of parallel image download threads (default: 10)",
    )
    parser.add_argument(
        "--download-timeout",
        type=int,
        default=10,
        help="Image download timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--model-name",
        default=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL),
        help="FastEmbed model to use for image embeddings",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    load_dotenv()

    qdrant_url = require_env("QDRANT_URL")
    qdrant_api_key = require_env("QDRANT_API_KEY")

    logging.info("Loading FastEmbed model '%s'...", args.model_name)
    model = ImageEmbedding(model_name=args.model_name)
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    
    samples = iter_samples(args.limit)
    
    # Use upload_points for efficient large-scale ingestion
    # For < 100k: batched upsert is fine
    # For 100k-1M: upload_points is recommended (what we use)
    # For > 1M: upload_collection (streaming) is ideal for raw vectors
    ingest_with_upload_points(
        client=client,
        collection_name=args.collection,
        model=model,
        samples=samples,
        embedding_batch_size=args.batch_size,
        upload_batch_size=args.upload_batch_size,
        parallel=args.parallel,
        total_items=args.limit,
        download_workers=args.download_workers,
        download_timeout=args.download_timeout,
    )
    
    # Get final count
    collection_info = client.get_collection(args.collection)
    logging.info(
        "Finished ingesting %d points into collection '%s'.",
        collection_info.points_count,
        args.collection,
    )


if __name__ == "__main__":
    main()

