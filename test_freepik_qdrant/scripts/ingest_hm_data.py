#!/usr/bin/env python3
"""
Ingest H&M Product Dataset into Qdrant
======================================
Load H&M product images from CSV and create vector embeddings for ad generation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator, List

import requests
from dotenv import load_dotenv
from fastembed import ImageEmbedding
from PIL import Image
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams


DEFAULT_COLLECTION = "hm-products"
DEFAULT_BATCH_SIZE = 32
DEFAULT_MODEL = "Qdrant/clip-ViT-B-32-vision"
DEFAULT_DOWNLOAD_WORKERS = 10
DEFAULT_DOWNLOAD_TIMEOUT = 15


def require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def normalize_image(image: Image.Image) -> Image.Image:
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def ensure_collection(client: QdrantClient, name: str, vector_size: int) -> None:
    collections = {c.name for c in client.get_collections().collections}
    if name in collections:
        logging.info(f"Collection '{name}' already exists")
        return
    logging.info(f"Creating collection '{name}' with vector size {vector_size}")
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def download_image(url: str, timeout: int = 15) -> Image.Image | None:
    """Download an image from a URL and return as PIL Image."""
    if not url or url.lower() == "null":
        return None
    try:
        response = requests.get(
            url,
            timeout=timeout,
            stream=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible)",
                "Accept": "image/*"
            }
        )
        response.raise_for_status()
        return Image.open(response.raw)
    except Exception as exc:
        logging.debug(f"Failed to download image from {url[:80]}: {exc}")
        return None


def download_images_parallel(
    urls: List[str],
    max_workers: int = 10,
    timeout: int = 15,
) -> List[Image.Image | None]:
    """Download multiple images in parallel."""
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
                logging.debug(f"Failed to download {url[:80]}: {exc}")
                results[url_to_index[url]] = None
        
        return results


def product_id_to_int(product_id: str) -> int:
    """Convert product_id string to a consistent integer ID."""
    return int(hashlib.md5(product_id.encode()).hexdigest()[:8], 16)


def parse_hm_csv(csv_path: str) -> Iterator[dict]:
    """Parse H&M CSV file and yield product records."""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse image_urls from JSON array string
            image_urls_raw = row.get('image_urls', '[]')
            try:
                if image_urls_raw and image_urls_raw != 'null':
                    image_urls = json.loads(image_urls_raw)
                else:
                    image_urls = []
            except json.JSONDecodeError:
                # Fallback to main_image
                main_image = row.get('main_image', '')
                image_urls = [main_image] if main_image and main_image != 'null' else []
            
            # Use first image or main_image
            if not image_urls:
                main_image = row.get('main_image', '')
                if main_image and main_image != 'null':
                    image_urls = [main_image]
            
            if not image_urls:
                logging.debug(f"No images for product {row.get('product_code', 'unknown')}")
                continue
            
            yield {
                'product_id': row.get('product_code', ''),
                'product_name': row.get('product_name', ''),
                'description': row.get('description', ''),
                'category': row.get('category', ''),
                'brand': row.get('brand', ''),
                'color': row.get('color', ''),
                'price': row.get('final_price', ''),
                'image_url': image_urls[0],  # Use first image
                'all_images': image_urls,
                'url': row.get('url', ''),
            }


def generate_points(
    model: ImageEmbedding,
    products: Iterator[dict],
    embedding_batch_size: int,
    total_items: int | None = None,
    download_workers: int = 10,
    download_timeout: int = 15,
) -> Iterator[PointStruct]:
    """Generate PointStruct objects for Qdrant from H&M products."""
    from tqdm import tqdm
    
    batch: List[dict] = []
    processed = 0
    skipped = 0
    progress = tqdm(total=total_items, desc="Processing H&M products", unit="products") if total_items else None
    
    for product in products:
        batch.append(product)
        if len(batch) < embedding_batch_size:
            continue
        
        # Download images in parallel
        image_urls = [p['image_url'] for p in batch]
        downloaded_images = download_images_parallel(
            image_urls,
            max_workers=download_workers,
            timeout=download_timeout,
        )
        
        # Filter successful downloads
        images: List[Image.Image] = []
        successful_products: List[dict] = []
        for img, product_item in zip(downloaded_images, batch):
            if img:
                images.append(normalize_image(img))
                successful_products.append(product_item)
            else:
                skipped += 1
                if progress:
                    progress.update(1)
        
        if images:
            # Generate embeddings
            embeddings = list(model.embed(images, batch_size=embedding_batch_size))
            
            # Yield points
            for product_item, emb in zip(successful_products, embeddings):
                product_id = product_item['product_id']
                processed += 1
                if progress:
                    progress.update(1)
                    progress.set_postfix(processed=processed, skipped=skipped)
                
                yield PointStruct(
                    id=product_id_to_int(product_id),
                    vector=emb.tolist(),
                    payload={
                        'product_id': product_id,
                        'product_name': product_item.get('product_name', ''),
                        'description': product_item.get('description', ''),
                        'category': product_item.get('category', ''),
                        'brand': product_item.get('brand', ''),
                        'color': product_item.get('color', ''),
                        'price': product_item.get('price', ''),
                        'image_url': product_item['image_url'],
                        'url': product_item.get('url', ''),
                    },
                )
        
        batch = []
    
    # Process remaining items
    if batch:
        image_urls = [p['image_url'] for p in batch]
        downloaded_images = download_images_parallel(
            image_urls,
            max_workers=download_workers,
            timeout=download_timeout,
        )
        
        images = []
        successful_products = []
        for img, product_item in zip(downloaded_images, batch):
            if img:
                images.append(normalize_image(img))
                successful_products.append(product_item)
            else:
                skipped += 1
                if progress:
                    progress.update(1)
        
        if images:
            embeddings = list(model.embed(images, batch_size=embedding_batch_size))
            for product_item, emb in zip(successful_products, embeddings):
                product_id = product_item['product_id']
                processed += 1
                if progress:
                    progress.update(1)
                    progress.set_postfix(processed=processed, skipped=skipped)
                
                yield PointStruct(
                    id=product_id_to_int(product_id),
                    vector=emb.tolist(),
                    payload={
                        'product_id': product_id,
                        'product_name': product_item.get('product_name', ''),
                        'description': product_item.get('description', ''),
                        'category': product_item.get('category', ''),
                        'brand': product_item.get('brand', ''),
                        'color': product_item.get('color', ''),
                        'price': product_item.get('price', ''),
                        'image_url': product_item['image_url'],
                        'url': product_item.get('url', ''),
                    },
                )
    
    if progress:
        progress.close()
        print(f"\n✅ Processed {processed} products ({skipped} skipped due to download failures)")


def ingest_hm_dataset(
    csv_path: str,
    client: QdrantClient,
    collection_name: str,
    model: ImageEmbedding,
    embedding_batch_size: int,
    upload_batch_size: int = 256,
    parallel: int = 4,
    download_workers: int = 10,
    download_timeout: int = 15,
) -> None:
    """Ingest H&M dataset into Qdrant."""
    
    # Count total products first
    total_items = sum(1 for _ in parse_hm_csv(csv_path))
    logging.info(f"Found {total_items} products in CSV")
    
    # Get vector size from a sample
    products_iter = parse_hm_csv(csv_path)
    first_product = next(products_iter)
    img = download_image(first_product['image_url'])
    if not img:
        raise ValueError("Failed to download sample image")
    test_emb = list(model.embed([normalize_image(img)], batch_size=1))[0]
    vector_size = len(test_emb)
    logging.info(f"Vector size: {vector_size}")
    
    # Ensure collection exists
    ensure_collection(client, collection_name, vector_size)
    
    # Generate points from all products (including the first one we already read)
    def all_products():
        yield first_product
        yield from parse_hm_csv(csv_path)
    
    points_generator = generate_points(
        model,
        all_products(),
        embedding_batch_size,
        total_items=total_items,
        download_workers=download_workers,
        download_timeout=download_timeout,
    )
    
    # Upload to Qdrant
    client.upload_points(
        collection_name=collection_name,
        points=points_generator,
        batch_size=upload_batch_size,
        parallel=parallel,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest H&M product dataset into Qdrant for ad generation."
    )
    parser.add_argument(
        "csv_path",
        help="Path to H&M dataset CSV file",
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION),
        help=f"Target Qdrant collection name (default: {DEFAULT_COLLECTION})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Embedding batch size (default: {DEFAULT_BATCH_SIZE})",
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
        default=DEFAULT_DOWNLOAD_WORKERS,
        help=f"Number of parallel image download threads (default: {DEFAULT_DOWNLOAD_WORKERS})",
    )
    parser.add_argument(
        "--download-timeout",
        type=int,
        default=DEFAULT_DOWNLOAD_TIMEOUT,
        help=f"Image download timeout in seconds (default: {DEFAULT_DOWNLOAD_TIMEOUT})",
    )
    parser.add_argument(
        "--model-name",
        default=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL),
        help=f"FastEmbed model for image embeddings (default: {DEFAULT_MODEL})",
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
    
    # Validate CSV file exists
    if not Path(args.csv_path).exists():
        raise FileNotFoundError(f"CSV file not found: {args.csv_path}")
    
    qdrant_url = require_env("QDRANT_URL")
    qdrant_api_key = require_env("QDRANT_API_KEY")
    
    logging.info(f"Loading FastEmbed model '{args.model_name}'...")
    model = ImageEmbedding(model_name=args.model_name)
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    
    ingest_hm_dataset(
        csv_path=args.csv_path,
        client=client,
        collection_name=args.collection,
        model=model,
        embedding_batch_size=args.batch_size,
        upload_batch_size=args.upload_batch_size,
        parallel=args.parallel,
        download_workers=args.download_workers,
        download_timeout=args.download_timeout,
    )
    
    # Get final count
    collection_info = client.get_collection(args.collection)
    logging.info(
        f"✅ Finished! Collection '{args.collection}' now has {collection_info.points_count} products."
    )


if __name__ == "__main__":
    main()
