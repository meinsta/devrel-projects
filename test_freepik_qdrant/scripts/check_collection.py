#!/usr/bin/env python3
"""Check what's actually in the Qdrant collection"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "shopping-queries-images")

print(f"🔍 Checking collection: {COLLECTION_NAME}")
print("=" * 80)

# Get collection info
try:
    collection_info = client.get_collection(COLLECTION_NAME)
    print(f"✅ Collection exists!")
    print(f"   Total points: {collection_info.points_count:,}")
    print(f"   Vector size: {collection_info.config.params.vectors.size}")
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

# Get a few sample points
print(f"\n📋 Sample products (first 5):")
print("=" * 80)

result = client.scroll(
    collection_name=COLLECTION_NAME,
    limit=5,
    with_payload=True,
    with_vectors=False,
)

points, _ = result

for i, point in enumerate(points, 1):
    print(f"\n{i}. Point ID: {point.id}")
    print(f"   Payload fields: {list(point.payload.keys())}")
    print(f"   Product ID: {point.payload.get('product_id')}")
    
    # Show all payload data
    for key, value in point.payload.items():
        if key not in ['product_id', 'image_url']:
            print(f"   {key}: {str(value)[:100]}")

print("\n" + "=" * 80)
print(f"💡 Your collection {'already has' if len(points[0].payload) > 2 else 'only has'} metadata beyond product_id and image_url")

if len(points[0].payload) > 2:
    print("✅ Looks like your collection is already enriched!")
else:
    print("⚠️  Collection only has basic data (product_id + image_url)")
    print("   To enrich, you'll need to download ESCI dataset manually")



