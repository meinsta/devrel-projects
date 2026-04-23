#!/usr/bin/env python3
"""
Simple FastAPI Backend - High-End Editorial Demo
===================================================
REST API for generating GQ/Fortune style advertisements.
Fixes: 'Floating Product' bugs and 'Cartoonish' text placements.
"""

import asyncio
import json
import os
from typing import Any
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import json
import asyncio

# Ensure agent.py is in the same directory
from agent import AdGenerationAgent

load_dotenv()

app = FastAPI(
    title="Ad Generation Agent API (Luxury Edition)",
    description="High-end editorial advertisement creation",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
agent = None

def get_agent():
    global agent
    if agent is None:
        agent = AdGenerationAgent(
            qdrant_url=os.getenv("QDRANT_URL"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            freepik_api_key=os.getenv("FREEPIK_API_KEY"),
        )
    return agent

class AdRequest(BaseModel):
    query: str
    num_products: int = 5
    num_images: int = 1

async def generate_ad_stream(request: AdRequest):
    """Generator function that yields progress updates"""
    try:
        agent = get_agent()
        
        # Step 1: Search & Reason - stream as it happens
        search_results_by_query = {}
        
        def search_progress_callback(progress_data):
            """Callback to stream search progress - called synchronously during search"""
            nonlocal search_results_by_query
            if progress_data['type'] == 'search_start':
                search_results_by_query[progress_data['query']] = []
            elif progress_data['type'] == 'search_complete':
                search_results_by_query[progress_data['query']] = progress_data['results']
        
        # Execute search with progress callback (this is synchronous, so callback happens during search)
        products = agent.search_products(request.query, limit=request.num_products, progress_callback=search_progress_callback)
        if not products:
            yield f"data: {json.dumps({'step': 'error', 'message': 'No products found', 'details': {'query': request.query}})}\n\n"
            return
        
        # Stream reasoning first (if available)
        reasoning = agent.last_reasoning or {}
        if reasoning:
            search_queries = reasoning.get('search_queries', [])
            yield f"data: {json.dumps({'step': 'reasoning', 'message': f'Analyzing query and creating {len(search_queries)} diverse product searches...', 'details': {'intent': reasoning.get('intent', 'N/A'), 'search_queries': search_queries, 'categories': reasoning.get('categories', []), 'features': reasoning.get('features', []), 'search_strategy': reasoning.get('search_strategy', 'N/A'), 'reasoning': reasoning.get('reasoning', 'N/A')}})}\n\n"
            await asyncio.sleep(0.1)
            
            # Stream each search query and its results
            for idx, search_query in enumerate(search_queries, 1):
                yield f"data: {json.dumps({'step': 'searching', 'message': f'Searching {idx}/{len(search_queries)}: "{search_query}"...', 'details': {'search_index': idx, 'total_searches': len(search_queries), 'query': search_query}})}\n\n"
                await asyncio.sleep(0.1)
                
                # Stream results for this search (collected via callback)
                if search_query in search_results_by_query:
                    results = search_results_by_query[search_query]
                    yield f"data: {json.dumps({'step': 'search_results', 'message': f'Found {len(results)} products for "{search_query}"', 'details': {'search_query': search_query, 'search_index': idx, 'results': results, 'count': len(results)}})}\n\n"
                    await asyncio.sleep(0.1)
        
        # Step 2: Generate Copy
        yield f"data: {json.dumps({'step': 'generating_copy', 'message': 'Creating editorial ad copy with world-class copywriting...', 'details': {'query': request.query, 'product_count': len(products)}})}\n\n"
        await asyncio.sleep(0.1)
        
        ad_copy = agent.generate_ad_copy(request.query, products, [])
        yield f"data: {json.dumps({'step': 'copy_generated', 'message': 'Ad copy created', 'details': {'headline': ad_copy.headline, 'body': ad_copy.body, 'call_to_action': ad_copy.call_to_action, 'full_copy': f"{ad_copy.headline}\n\n{ad_copy.body}\n\n{ad_copy.call_to_action}"}})}\n\n"
        await asyncio.sleep(0.1)
        
        # Step 3: Generate Single Prompt with ALL Products (one from each search)
        yield f"data: {json.dumps({'step': 'generating_prompts', 'message': f'Creating single image prompt with all {len(products)} products (one from each search)...', 'details': {'query': request.query, 'num_products': len(products), 'products': [p.product_id for p in products]}})}\n\n"
        await asyncio.sleep(0.1)
        
        # Generate a single prompt that includes ALL products
        prompt_data = agent.generate_image_prompt_with_all_products(request.query, products, ad_copy)
        
        yield f"data: {json.dumps({'step': 'prompts_generated', 'message': f'Generated single prompt including all {len(products)} products', 'details': {'count': 1, 'products_included': [p.product_id for p in products], 'prompt_preview': prompt_data.get('prompt', '')[:200] + '...'}})}\n\n"
        await asyncio.sleep(0.1)
        
        # Step 4: Generate Single Image with ALL Products
        yield f"data: {json.dumps({'step': 'generating_image', 'message': f'Generating single ad image with all {len(products)} products...', 'details': {'products': [p.product_id for p in products], 'prompt_preview': prompt_data.get('prompt', '')[:150] + '...'}})}\n\n"
        await asyncio.sleep(0.1)
        
        base_prompt = prompt_data.get("prompt", "")
        short_headline = ad_copy.headline[:40]
        surface_material = "dark polished marble"
        if "wood" in base_prompt or "natural" in request.query:
            surface_material = "rich mahogany wood"
        elif "tech" in request.query or "modern" in base_prompt:
            surface_material = "brushed aluminum or textured concrete"

        enhanced_prompt = f"""
[STYLE: HIGH-END MAGAZINE EDITORIAL]

1. THE SETUP (GROUNDING)
- ALL Products ({base_prompt}) are SITTING ON a {surface_material} surface.
- GRAVITY: All products must rest firmly on surfaces. They must cast realistic contact shadows. 
- DO NOT let any products float in mid-air.
- DO NOT use podiums or stages. Make it look like a lifestyle photoshoot.

2. THE COMPOSITION (MINIMALIST)
- Angle: Eye-level or 45-degree product shot.
- Framing: Arrange all products naturally in the scene (bottom-right, bottom-center, or distributed).
- Negative Space: The top-left 60% of the image is clean, blurred background (Bokeh) or solid wall.

3. TYPOGRAPHY (OVERLAY)
- Treat the text as a GQ/Fortune magazine headline.
- Text: "{short_headline}"
- Font: Elegant Serif (like Didot or Bodoni) or Ultra-Bold Sans.
- Placement: Floating in the Negative Space (Top Left).
- Color: White or Metallic Gold (High Contrast).

4. LIGHTING & MOOD
- Lighting: Dramatic "Chiaroscuro" or "Rembrandt" lighting.
- Shadows: Sharp and deep.
- Aesthetic: Expensive, Sophisticated, Award-Winning Photography.
- Resolution: 8k, Hasselblad Medium Format quality.
"""
        
        # Get reference images for ALL products (one from each search)
        # Use data URLs we already have from Qdrant, or extract base64 from them
        reference_images_data = []
        for product in products:
            # Prefer data URL if we already have it (downloaded from Qdrant)
            if product.image_url and product.image_url.startswith('data:'):
                # Extract base64 from data URL
                try:
                    header, encoded = product.image_url.split(',', 1)
                    reference_images_data.append(encoded)  # Just the base64 part
                    print(f"   ✅ Using existing data URL for product {product.product_id} (base64: {len(encoded)} chars)")
                except:
                    print(f"   ⚠️  Could not extract base64 from data URL for {product.product_id}")
            else:
                # Fallback: try to download from URL
                reference_url = getattr(product, 'original_image_url', None) or product.image_url
                if reference_url:
                    reference_images_data.append(('url', reference_url))  # Mark as URL to download
        
        yield f"data: {json.dumps({'step': 'image_processing', 'message': f'Rendering image with Freepik using {len(reference_images_data)} product references...', 'details': {'num_references': len(reference_images_data), 'products': [p.product_id for p in products], 'using_nano_banana': True, 'reference_url': 'Nano Banana product images from Qdrant'}})}\n\n"
        await asyncio.sleep(0.1)
        
        # Generate single image with all product references
        # Pass first as main reference, rest as additional
        result = agent.generate_image_with_freepik(
            enhanced_prompt, 
            reference_images_data[0] if reference_images_data else None, 
            additional_references=reference_images_data[1:] if len(reference_images_data) > 1 else []
        )
        
        if result:
            yield f"data: {json.dumps({'step': 'image_converting', 'message': 'Converting image to data URL for display...', 'details': {'task_id': result.task_id, 'status': result.status, 'products': len(products)}})}\n\n"
            await asyncio.sleep(0.1)
            
            display_image_urls = []
            
            for img_url in result.image_urls:
                if not img_url:
                    continue
                
                # Check if URL is already a data URL
                if img_url.startswith('data:'):
                    display_image_urls.append(img_url)
                    continue
                
                # For regular URLs, try to download but don't fail if it doesn't work
                # Freepik URLs may work directly in browser even if server-side download fails
                try:
                    import requests
                    import base64
                    import os
                    # Add proper headers with Freepik API key for authentication
                    freepik_api_key = os.getenv("FREEPIK_API_KEY", "")
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': 'https://www.freepik.com/',
                        'Origin': 'https://www.freepik.com',
                        'Accept-Encoding': 'gzip, deflate, br'
                    }
                    # Add API key if available (for signed URLs that require auth)
                    if freepik_api_key:
                        headers['x-freepik-api-key'] = freepik_api_key
                    
                    print(f"   Attempting to download image from: {img_url[:80]}...")
                    img_response = requests.get(
                        img_url, 
                        timeout=20, 
                        headers=headers,
                        allow_redirects=True,
                        stream=True  # Stream for better handling
                    )
                    
                    if img_response.status_code == 200:
                        img_content = img_response.content
                        img_base64 = base64.b64encode(img_content).decode('utf-8')
                        content_type = img_response.headers.get('Content-Type', 'image/jpeg')
                        # Determine content type from URL or response
                        if 'png' in content_type.lower() or img_url.lower().endswith('.png'):
                            data_url = f"data:image/png;base64,{img_base64}"
                        elif 'webp' in content_type.lower() or img_url.lower().endswith('.webp'):
                            data_url = f"data:image/webp;base64,{img_base64}"
                        else:
                            data_url = f"data:image/jpeg;base64,{img_base64}"
                        display_image_urls.append(data_url)
                        print(f"   ✅ Converted image to data URL ({len(data_url)} chars)")
                        
                        # Verify image with Gemini vision (check for all products)
                    else:
                        # Download failed - use URL directly (browser may handle it better)
                        print(f"   ⚠️  Server-side download failed ({img_response.status_code}), using URL directly")
                        print(f"   URL: {img_url[:100]}")
                        display_image_urls.append(img_url)
                except Exception as e:
                    # Error downloading - use URL directly
                    print(f"   ⚠️  Error downloading image: {str(e)[:100]}")
                    print(f"   Using URL directly (may work in browser): {img_url[:100]}")
                    display_image_urls.append(img_url)
            
            generated_images = []
            generated_images.append({
                "task_id": result.task_id,
                "prompt": enhanced_prompt,
                "status": result.status,
                "image_urls": display_image_urls if display_image_urls else result.image_urls,
                "reference_image_url": result.reference_image_url,
            })
            
            yield f"data: {json.dumps({'step': 'image_complete', 'message': f'Single ad image with all {len(products)} products generated successfully', 'details': {'task_id': result.task_id, 'status': result.status, 'has_image_urls': len(display_image_urls) > 0, 'image_count': len(display_image_urls), 'products_included': len(products)}})}\n\n"
            await asyncio.sleep(0.1)
        else:
            yield f"data: {json.dumps({'step': 'image_error', 'message': 'Failed to generate image', 'details': {}})}\n\n"
            await asyncio.sleep(0.1)
        
        # Final result - include reasoning and product search results
        product_details = [
            {
                'product_id': p.product_id,
                'image_url': p.image_url,
                'score': round(p.score, 4),
                'match_percentage': f"{round(p.score * 100, 1)}%"
            }
            for p in products
        ]
        
        final_ad_data = {
            'query': request.query,
            'timestamp': datetime.now().isoformat(),
            'reasoning': reasoning,
            'ad_copy': {
                'headline': ad_copy.headline,
                'body': ad_copy.body,
                'call_to_action': ad_copy.call_to_action
            },
            'products': product_details,
            'generated_images': generated_images,
            'search_results': {
                'count': len(products),
                'products': product_details,
                'top_match': product_details[0] if product_details else None
            }
        }
        
        # Save to history
        try:
            history_dir = Path("history")
            history_dir.mkdir(exist_ok=True)
            
            # Create filename from timestamp and query
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = "".join([c if c.isalnum() else "_" for c in request.query])[:30]
            filename = f"{timestamp}_{safe_query}.json"
            
            with open(history_dir / filename, "w") as f:
                json.dump(final_ad_data, f, indent=2)
                
            print(f"✅ Saved ad history to {filename}")
        except Exception as e:
            print(f"⚠️ Failed to save history: {e}")
            
        yield f"data: {json.dumps({'step': 'complete', **final_ad_data})}\n\n"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"


@app.post("/api/create-ad")
async def create_ad(request: AdRequest):
    """Streaming endpoint for ad creation"""
    return StreamingResponse(
        generate_ad_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@app.get("/api/history")
async def get_history():
    """Get list of generated ads"""
    try:
        history_dir = Path("history")
        if not history_dir.exists():
            return []
            
        files = []
        for f in history_dir.glob("*.json"):
            try:
                stat = f.stat()
                # Read just enough to get the query and timestamp
                with open(f, "r") as json_file:
                    data = json.load(json_file)
                    files.append({
                        "filename": f.name,
                        "query": data.get("query", "Unknown"),
                        "timestamp": data.get("timestamp", stat.st_mtime),
                        "headline": data.get("ad_copy", {}).get("headline", ""),
                        "image_url": data.get("generated_images", [{}])[0].get("image_urls", [""])[0] if data.get("generated_images") else ""
                    })
            except Exception as e:
                print(f"Error reading {f}: {e}")
                continue
                
        # Sort by timestamp descending
        return sorted(files, key=lambda x: x["timestamp"], reverse=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history/{filename}")
async def get_history_item(filename: str):
    """Get a specific ad from history"""
    try:
        history_dir = Path("history")
        file_path = history_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="History item not found")
            
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Ensure history dir exists
    Path("history").mkdir(exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8001)