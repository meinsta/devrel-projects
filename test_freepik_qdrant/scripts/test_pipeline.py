#!/usr/bin/env python3
"""
Simple Pipeline Test - Without ADK Framework
==============================================
Tests complete workflow using the original agent.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Import the simple agent
from agent import AdGenerationAgent

async def test_pipeline():
    """Test full pipeline."""
    load_dotenv()
    
    print("=" * 80)
    print("🚀 SIMPLE PIPELINE TEST")
    print("=" * 80)
    
    # Check environment
    required = {
        "QDRANT_URL": os.getenv("QDRANT_URL"),
        "QDRANT_API_KEY": os.getenv("QDRANT_API_KEY"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "FREEPIK_API_KEY": os.getenv("FREEPIK_API_KEY"),
    }
    
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")
        return False
    
    print("\n✓ All environment variables set")
    
    # Initialize agent
    print("\n[Step 1] Initializing Agent...")
    agent = AdGenerationAgent(
        qdrant_url=required["QDRANT_URL"],
        qdrant_api_key=required["QDRANT_API_KEY"],
        gemini_api_key=required["GEMINI_API_KEY"],
        freepik_api_key=required["FREEPIK_API_KEY"],
    )
    print("✓ Agent initialized")
    
    # Run pipeline
    query = "hiking adventure gear"
    print(f"\n[Step 2] Running Pipeline for: '{query}'")
    print("-" * 80)
    
    # Search products
    print("\n🔍 Searching Qdrant...")
    products = agent.search_products(query, limit=5)
    print(f"✓ Found {len(products)} products from Nano Banana:")
    for i, p in enumerate(products[:3], 1):
        print(f"  {i}. Product {p.product_id} (score: {p.score:.4f})")
    
    # Generate image prompts
    print("\n🤖 Generating image prompts with Gemini...")
    prompts = agent.generate_image_prompts(query, products, num_prompts=1)
    print(f"✓ Generated {len(prompts)} prompt(s):")
    for i, p in enumerate(prompts, 1):
        print(f"  {i}. {p['description']}")
        print(f"     Reference: {p.get('product_reference', 'none')}")
    
    # Generate images
    print("\n🎨 Generating images with Freepik...")
    print("(This may take 30-60 seconds...)")
    
    generated_images = []
    for prompt_data in prompts[:1]:  # Just 1 image for testing
        prompt = prompt_data.get("prompt", "")
        product_ref = prompt_data.get("product_reference", "none")
        
        # Find reference URL
        reference_url = None
        if product_ref != "none":
            for product in products:
                if product.product_id == product_ref:
                    reference_url = product.image_url
                    break
        
        result = agent.generate_image_with_freepik(prompt, reference_url)
        if result:
            generated_images.append(result)
            if result.status == "completed":
                print(f"✓ Image generated: {len(result.image_urls)} URL(s)")
            else:
                print(f"⚠️  Image status: {result.status}")
    
    # Generate ad copy
    print("\n✍️  Generating ad copy with Gemini...")
    ad_copy = agent.generate_ad_copy(query, products, generated_images)
    print(f"✓ Ad copy created:")
    print(f"  Headline: {ad_copy.headline}")
    print(f"  CTA: {ad_copy.call_to_action}")
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ PIPELINE TEST COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Results:")
    print(f"  • Query: {query}")
    print(f"  • Products from Nano Banana: {len(products)}")
    print(f"  • Images generated: {len([i for i in generated_images if i.status == 'completed'])}")
    print(f"  • Ad copy: Complete")
    
    print(f"\n🎯 Full Advertisement:")
    print(f"\n  📢 {ad_copy.headline}")
    print(f"  📝 {ad_copy.body}")
    print(f"  🎯 {ad_copy.call_to_action}")
    
    if products:
        print(f"\n  🛍️  Products:")
        for p in products[:3]:
            print(f"     • {p.product_id} ({p.score*100:.1f}% match)")
    
    if generated_images:
        print(f"\n  🖼️  Generated Images:")
        for i, img in enumerate(generated_images, 1):
            if img.status == "completed" and img.image_urls:
                print(f"     • Image {i}: {img.image_urls[0][:60]}...")
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_pipeline())
        if success:
            print("\n✅ SUCCESS!")
        else:
            print("\n❌ FAILED")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()



