#!/usr/bin/env python3
"""
Ad Generation Agent - Production Workflow
==========================================
Complete pipeline for generating advertisements:
1. Takes an ad query from user
2. Searches Qdrant vector database for relevant products
   - H&M product images (1000+ fashion and home items)
3. Sends product images to Freepik API to generate ad visuals
4. Uses Gemini to create compelling ad copy
5. Assembles and saves the complete advertisement

Usage:
    python agent.py "summer fashion collection"
    python agent.py "winter coats" --num-products 3
"""

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google import genai
import requests
from dotenv import load_dotenv
from fastembed import TextEmbedding
from PIL import Image, ImageDraw, ImageFont
from qdrant_client import QdrantClient
import io
import base64


@dataclass
class Product:
    """Represents a product from the vector database."""
    product_id: str
    image_url: str  # Can be data URL or regular URL
    score: float
    original_image_url: str | None = None  # Store original URL for Freepik reference


@dataclass
class GeneratedImage:
    """Represents a generated ad image."""
    task_id: str
    prompt: str
    reference_image_url: str | None
    status: str
    image_urls: list[str]
    error: str | None = None


@dataclass
class AdCopy:
    """Represents the ad copy."""
    headline: str
    body: str
    call_to_action: str
    image_suggestions: str


class AdGenerationAgent:
    """
    Agent that orchestrates the complete ad generation workflow.
    """
    
    def __init__(
        self,
        qdrant_url: str,
        qdrant_api_key: str,
        gemini_api_key: str,
        freepik_api_key: str,
        collection_name: str = "hm-products",
        text_model: str = "Qdrant/clip-ViT-B-32-text",
        gemini_model: str = "gemini-2.0-flash-exp",
        freepik_model: str = "text-to-image",
    ):
        """Initialize the agent with API credentials and model configurations."""
        self.collection_name = collection_name
        self.text_model_name = text_model
        self.gemini_model = gemini_model
        self.freepik_model = freepik_model
        self.freepik_api_key = freepik_api_key
        self.last_reasoning = None  # Store last query reasoning
        
        # Initialize clients
        self.qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self.text_model = TextEmbedding(model_name=text_model)
        # Initialize Gemini client (new SDK)
        self.gemini_client = genai.Client(api_key=gemini_api_key)
        
        print("✓ Ad Generation Agent initialized")
        print(f"  Qdrant Collection: {collection_name}")
        print(f"  Text Model: {text_model}")
        print(f"  Gemini Model: {gemini_model}")
        print(f"  Freepik Model: {freepik_model}")
    
    def search_products(self, query: str, limit: int = 5, progress_callback=None) -> list[Product]:
        """
        Search Qdrant vector database for relevant products using multiple diverse searches.
        
        Product images are from the H&M product dataset (1000+ fashion and home items).
        
        Args:
            query: Search query text
            limit: Total number of products to return (will be distributed across searches)
            
        Returns:
            List of Product objects with diversity
        """
        print(f"\n🔍 Step 1: Analyzing query and creating diverse product searches...")
        print("-" * 70)
        
        # Agent reasoning: Break down the query into multiple search queries
        print(f"\n💭 Agent Reasoning:")
        print(f"   Query: '{query}'")
        print(f"   Breaking down into multiple product searches for diversity...")
        
        # Use Gemini to break down the query into multiple specific product searches
        reasoning_prompt = f"""Analyze this search query and break it down into 3-5 specific product search queries that will find diverse products:

Original Query: "{query}"

Your goal is to create multiple search queries that will find DIFFERENT types of products related to the query, not just variations of the same product.

For example:
- If query is "running shoes for marathon training", create searches like:
  - "marathon running shoes"
  - "training running shoes"
  - "long distance running shoes"
  - "performance running footwear"
  
- If query is "outdoor camping gear", create searches like:
  - "camping tents"
  - "camping sleeping bags"
  - "camping cooking equipment"
  - "camping backpacks"

Return JSON with:
- "intent": string (main intent)
- "search_queries": array of 3-5 specific search query strings (each should target different product types/variations)
- "categories": array of strings (product categories identified)
- "features": array of strings (important features)
- "reasoning": string (explanation of why these searches will find diverse products)

Make sure the search queries are:
1. Specific enough to find relevant products
2. Different enough to find diverse products
3. Related to the original query
"""
        
        try:
            reasoning_response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
                contents=reasoning_prompt,
                config={
                    "temperature": 0.7,
                    "response_mime_type": "application/json"
                }
            )
            
            reasoning_text = reasoning_response.text.strip()
            if "```json" in reasoning_text:
                reasoning_text = reasoning_text.split("```json")[1].split("```")[0].strip()
            elif "```" in reasoning_text:
                reasoning_text = reasoning_text.split("```")[1].split("```")[0].strip()
            
            reasoning_data = json.loads(reasoning_text)
            
            search_queries = reasoning_data.get('search_queries', [query])  # Fallback to original query
            if not search_queries or len(search_queries) == 0:
                search_queries = [query]
            
            print(f"   ✅ Intent: {reasoning_data.get('intent', 'N/A')}")
            print(f"   ✅ Generated {len(search_queries)} diverse search queries:")
            for i, sq in enumerate(search_queries, 1):
                print(f"      {i}. '{sq}'")
            print(f"   ✅ Categories: {', '.join(reasoning_data.get('categories', []))}")
            print(f"   ✅ Features: {', '.join(reasoning_data.get('features', []))}")
            print(f"   💡 Reasoning: {reasoning_data.get('reasoning', 'N/A')}")
            
            # Store reasoning with search queries
            self.last_reasoning = {
                **reasoning_data,
                "search_queries": search_queries,
                "search_strategy": f"Multiple diverse searches ({len(search_queries)} queries)"
            }
            
        except Exception as e:
            print(f"   ⚠️  Could not analyze query: {e}")
            import traceback
            traceback.print_exc()
            search_queries = [query]  # Fallback to single search
            self.last_reasoning = {
                "intent": query,
                "search_queries": search_queries,
                "categories": [],
                "features": [],
                "search_strategy": "Single direct search",
                "reasoning": "Using direct query search (fallback)"
            }
        
        # Calculate products per search (distribute limit across searches)
        products_per_search = max(2, limit // len(search_queries))  # At least 2 per search
        print(f"\n🔎 Executing {len(search_queries)} diverse searches...")
        print(f"   Collection: {self.collection_name}")
        print(f"   Products per search: {products_per_search}")
        print(f"   Target total: {limit} products")
        
        # Execute multiple searches and combine results
        # Track products by search query to select one from each
        products_by_search = {}
        seen_product_ids = set()  # Deduplicate by product_id
        
        for idx, search_query in enumerate(search_queries, 1):
            print(f"\n   Search {idx}/{len(search_queries)}: '{search_query}'")
            
            # Notify progress callback about search starting
            if progress_callback:
                progress_callback({
                    'type': 'search_start',
                    'search_index': idx,
                    'total_searches': len(search_queries),
                    'query': search_query
                })
            
            # Initialize list for this search query
            if search_query not in products_by_search:
                products_by_search[search_query] = []
            
            try:
                # Generate embedding for this search query
                query_embedding = list(self.text_model.embed([search_query]))[0]
                
                # Search Qdrant with this query
                result = self.qdrant_client.query_points(
                    collection_name=self.collection_name,
                    query=query_embedding.tolist(),
                    limit=products_per_search + 2,  # Get a few extra to account for duplicates
                )
                
                # Parse results and deduplicate
                new_products = 0
                search_results = []  # Collect results for this search
                for point in result.points:
                    payload = point.payload or {}
                    product_id = payload.get("product_id", "N/A")
                    
                    # Skip if we've already seen this product
                    if product_id in seen_product_ids:
                        continue
                    
                    seen_product_ids.add(product_id)
                    image_url = payload.get("image_url", "N/A")
                    
                    # Download image and convert to base64 data URL to avoid CORS/bad request issues
                    image_data_url = None
                    if image_url and image_url != "N/A" and not image_url.startswith('data:'):
                        # Fix missing .jpg extension
                        if not image_url.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                            image_url = image_url.rstrip('/') + '.jpg'
                        
                        try:
                            print(f"   Downloading image from Qdrant: {image_url[:60]}...")
                            img_response = requests.get(
                                image_url, 
                                timeout=10, 
                                headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                                    'Accept-Language': 'en-US,en;q=0.9',
                                    'Referer': 'https://www.amazon.com/'
                                },
                                allow_redirects=True
                            )
                            if img_response.status_code == 200:
                                import base64
                                img_base64 = base64.b64encode(img_response.content).decode('utf-8')
                                # Determine content type
                                content_type = img_response.headers.get('Content-Type', 'image/jpeg')
                                if 'png' in content_type.lower() or image_url.lower().endswith('.png'):
                                    image_data_url = f"data:image/png;base64,{img_base64}"
                                elif 'webp' in content_type.lower() or image_url.lower().endswith('.webp'):
                                    image_data_url = f"data:image/webp;base64,{img_base64}"
                                else:
                                    image_data_url = f"data:image/jpeg;base64,{img_base64}"
                                print(f"   ✅ Image downloaded and converted to data URL ({len(image_data_url)} chars)")
                            else:
                                print(f"   ⚠️  Failed to download image: HTTP {img_response.status_code}, using original URL")
                        except Exception as e:
                            print(f"   ⚠️  Error downloading image: {str(e)[:100]}, using original URL")
                    
                    # Store both: data URL for frontend display, original URL for Freepik reference
                    original_url = image_url
                    if not original_url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        original_url = original_url.rstrip('/') + '.png'
                    
                    product = Product(
                        product_id=product_id,
                        image_url=image_data_url or image_url,  # Use data URL if available, fallback to URL
                        original_image_url=original_url,  # Store original URL with proper extension for Freepik
                        score=round(point.score, 4),
                    )
                    # Add to this search query's products
                    products_by_search[search_query].append(product)
                    search_results.append({
                        'product_id': product.product_id,
                        'image_url': product.image_url,
                        'score': product.score,
                        'match_percentage': f"{round(product.score * 100, 1)}%"
                    })
                    new_products += 1
                    
                    # Stop if we have enough products from this search
                    if len(products_by_search[search_query]) >= products_per_search:
                        break
                
                print(f"   ✅ Found {new_products} new products from this search")
                
                # Notify progress callback about search results
                if progress_callback:
                    progress_callback({
                        'type': 'search_complete',
                        'search_index': idx,
                        'query': search_query,
                        'products_found': new_products,
                        'results': search_results
                    })
                    
            except Exception as e:
                print(f"   ⚠️  Error in search '{search_query}': {e}")
                continue
        
        print(f"\n   ✅ Qdrant searches completed")
        
        # Select one best product from each search query for diversity
        selected_products = []
        for search_query, search_products in products_by_search.items():
            if search_products:
                # Sort by score and take the best one from this search
                search_products.sort(key=lambda p: p.score, reverse=True)
                selected_products.append(search_products[0])
                print(f"   Selected from '{search_query}': Product {search_products[0].product_id} (score: {search_products[0].score:.3f})")
        
        # Sort all selected products by score and limit
        selected_products.sort(key=lambda p: p.score, reverse=True)
        products = selected_products[:limit]
        
        print(f"\n✓ Selected {len(products)} diverse products (one from each of {len(products_by_search)} searches):")
        for i, product in enumerate(products, 1):
            print(f"  {i}. Product {product.product_id} (relevance: {product.score:.3f})")
            if product.image_url.startswith('data:'):
                print(f"     Image: [Base64 data URL - {len(product.image_url)} chars]")
            else:
                print(f"     Image URL: {product.image_url[:60]}...")
        
        return products
    
    def generate_image_prompts(
        self,
        query: str,
        products: list[Product],
        num_prompts: int = 2,
    ) -> list[dict[str, str]]:
        """
        Use Gemini to analyze products and create image generation prompts.
        
        Args:
            query: Original search query
            products: List of Product objects
            num_prompts: Number of prompts to generate
            
        Returns:
            List of prompt dictionaries
        """
        print(f"\n🤖 Step 2: Generating {num_prompts} image prompts with Gemini...")
        print("-" * 70)
        
        # Prepare product context with image URLs
        product_details = []
        for p in products[:5]:  # Use up to 5 products
            product_details.append(
                f"- Product {p.product_id} (relevance: {p.score:.2%})\n"
                f"  Image: {p.image_url}"
            )
        product_summary = "\n".join(product_details)
        
        # Add reasoning context if available
        reasoning_context = ""
        if hasattr(self, 'last_reasoning') and self.last_reasoning:
            reasoning_context = f"\n\nQuery Analysis:\n- Intent: {self.last_reasoning.get('intent', '')}\n- Categories: {', '.join(self.last_reasoning.get('categories', []))}\n- Strategy: {self.last_reasoning.get('search_strategy', '')}"
        
        prompt = f"""You are a creative director and world-class photographer creating realistic advertisement images.

Search Query: "{query}"
{reasoning_context}

Relevant Products (with images):
{product_summary}

Create {num_prompts} compelling image generation prompts for advertisement visuals. CRITICAL COMPOSITION REQUIREMENTS:

1. **REALISTIC COMPOSITION**: Products must be placed naturally in the scene:
   - Products should be on surfaces (ground, table, shelf, etc.) - NOT floating
   - Products should follow physics (gravity, shadows, lighting)
   - Products should interact naturally with the environment
   - Unless the ad concept specifically calls for surreal/creative floating, keep it realistic

2. **NATURAL PLACEMENT**: 
   - Shoes: on feet, on floor, on a surface - never floating
   - Bags/backpacks: on shoulders, on ground, on a surface - naturally positioned
   - Clothing: on people, on hangers, folded on surfaces
   - Accessories: in use, on surfaces, naturally positioned

3. **SCENE COMPOSITION**:
   - Describe the environment (indoor/outdoor, setting, background)
   - Explain how products are integrated into the scene
   - Include realistic lighting, shadows, and perspective
   - Show products in context (being used, displayed naturally, etc.)

4. **PRODUCT VISIBILITY**:
   - Products should be clearly visible and prominent
   - Include specific details from the product images
   - Show products from angles that make sense in the scene

5. **LIFESTYLE INTEGRATION**:
   - Create a believable lifestyle scene
   - Products should feel naturally part of the environment
   - Avoid unrealistic or impossible product positions

Return a JSON array with objects containing:
- "prompt": The detailed image generation prompt (must describe realistic composition and natural product placement)
- "product_reference": Product ID to use as the main reference image (choose from the products above)
- "description": Brief explanation of the composition approach

Format: [{{"prompt": "...", "product_reference": "...", "description": "..."}}, ...]

Example of good composition: "A person hiking on a mountain trail, wearing hiking boots that are firmly planted on rocky ground. The backpack is on their shoulders, naturally positioned. The scene shows realistic lighting, shadows cast by the person and gear, and products integrated naturally into the outdoor environment."

Example of bad composition: "Hiking boots floating in the air above a mountain trail" (unless specifically a surreal ad concept)"""

        try:
            # Use new SDK client
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
                contents=prompt
            )
            
            # Extract JSON from response (new SDK returns .text directly)
            response_text = response.text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            prompts = json.loads(response_text)
            
            print(f"✓ Generated {len(prompts)} image prompts:")
            for i, p in enumerate(prompts, 1):
                print(f"  {i}. {p.get('description', 'N/A')}")
                print(f"     Reference: Product {p.get('product_reference', 'none')}")
            
            return prompts
            
        except Exception as e:
            print(f"⚠️  Error generating prompts: {e}")
            # Fallback prompt
            return [{
                "prompt": f"Professional product photography for {query}, modern and vibrant advertisement style, high quality, commercial photography",
                "product_reference": products[0].product_id if products else "none",
                "description": "Main advertising visual",
            }]
    
    def generate_image_prompt_with_all_products(
        self,
        query: str,
        products: list[Product],
        ad_copy: Any,
    ) -> dict[str, str]:
        """
        Generate a single image prompt that includes ALL products (one from each search).
        
        Args:
            query: Original search query
            products: List of Product objects (one from each search)
            ad_copy: AdCopy object with headline, body, CTA
            
        Returns:
            Prompt dictionary with prompt and product references
        """
        print(f"\n🤖 Generating single image prompt with all {len(products)} products...")
        print("-" * 70)
        
        # Prepare product context
        product_details = []
        for i, p in enumerate(products, 1):
            product_details.append(
                f"Product {i} (ID: {p.product_id}, relevance: {p.score:.2%})"
            )
        product_summary = "\n".join(product_details)
        
        # Add reasoning context if available
        reasoning_context = ""
        if hasattr(self, 'last_reasoning') and self.last_reasoning:
            search_queries = self.last_reasoning.get('search_queries', [])
            reasoning_context = f"\n\nQuery Analysis:\n- Intent: {self.last_reasoning.get('intent', '')}\n- Search Queries: {', '.join(search_queries)}\n- Categories: {', '.join(self.last_reasoning.get('categories', []))}"
        
        prompt_text = f"""You are a creative director creating a single, cohesive advertisement image that features ALL {len(products)} products together in one realistic scene.

Search Query: "{query}"
{reasoning_context}

Products to Include (one from each search):
{product_summary}

Ad Copy:
- Headline: {ad_copy.headline}
- Body: {ad_copy.body}
- CTA: {ad_copy.call_to_action}

Create a detailed image generation prompt that:
1. Features ALL {len(products)} products naturally integrated into ONE scene
2. Shows products in realistic positions (on surfaces, in use, naturally placed)
3. Creates a cohesive lifestyle scene that makes sense for all products together
4. Ensures all products are clearly visible and prominent
5. Describes realistic composition, lighting, and environment

The prompt should describe how all products work together in a single, believable scene.

Return JSON with:
- "prompt": The detailed image generation prompt describing the scene with all products
- "description": Brief explanation of how the products are integrated

Format: {{"prompt": "...", "description": "..."}}"""
        
        try:
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
                contents=prompt_text,
                config={
                    "temperature": 0.7,
                    "response_mime_type": "application/json"
                }
            )
            
            response_text = response.text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            prompt_data = json.loads(response_text)
            print(f"✓ Generated prompt including all {len(products)} products:")
            print(f"  {prompt_data.get('description', 'N/A')}")
            
            return prompt_data
            
        except Exception as e:
            print(f"⚠️  Error generating prompt: {e}")
            # Fallback prompt
            product_list = ", ".join([f"product {p.product_id}" for p in products])
            return {
                "prompt": f"Professional lifestyle advertisement featuring {product_list} arranged naturally on a surface, modern and vibrant style, high quality, commercial photography",
                "description": f"Lifestyle scene with {len(products)} products"
            }
    
    def generate_image_with_freepik(
        self,
        prompt: str,
        reference_image_url: str | None = None,
        additional_references: list[str] | None = None,
    ) -> GeneratedImage | None:
        """
        Generate an image using Freepik API with Nano Banana product image as reference.
        
        Args:
            prompt: Image generation prompt
            reference_image_url: Nano Banana product image URL to use as reference
            
        Returns:
            GeneratedImage object with generated image URL
        """
        print(f"\n🎨 Generating image with Freepik using Nano Banana product as reference...")
        print(f"   Prompt: {prompt[:80]}...")
        
        if not reference_image_url:
            print(f"⚠️  No reference image provided, skipping")
            return GeneratedImage(
                task_id="none",
                prompt=prompt,
                reference_image_url=None,
                status="skipped",
                image_urls=[],
                error="No reference image",
            )
        
        print(f"   Reference image (from Qdrant/Nano Banana): {reference_image_url[:60]}...")
        
        # Use Freepik Nano Banana (Gemini 2.5 Flash) API which supports reference images
        # This will actually incorporate the Nano Banana product image into the generated ad
        headers = {
            "x-freepik-api-key": self.freepik_api_key,
            "Content-Type": "application/json",
        }
        
        # Enhance prompt to ensure product is visible and explicitly use reference images
        # Nano Banana (Gemini 2.5 Flash) uses reference_images to incorporate product images
        enhanced_prompt = f"{prompt}\n\nThe image MUST incorporate and feature the products from the provided reference images. Use the reference images to accurately represent the products in the scene."
        
        # Use Gemini 2.5 Flash (Nano Banana) which accepts reference_images (base64)
        # reference_image_url and additional_references can be:
        # - Base64 strings (already extracted from data URLs)
        # - URLs (need to download and convert)
        reference_images = []
        all_references = []
        if reference_image_url:
            all_references.append(reference_image_url)
        if additional_references:
            all_references.extend(additional_references)
        
        # Process references: if base64 string, use directly; if URL, download and convert
        print(f"   Processing {len(all_references)} product reference image(s)...")
        for ref in all_references[:3]:  # Limit to 3 as per Freepik API
            if isinstance(ref, tuple) and ref[0] == 'url':
                # This is a URL that needs downloading
                ref_url = ref[1]
                try:
                    img_response = requests.get(
                        ref_url,
                        timeout=15,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                            'Referer': 'https://www.amazon.com/'
                        },
                        allow_redirects=True
                    )
                    if img_response.status_code == 200:
                        import base64 as b64
                        img_base64 = b64.b64encode(img_response.content).decode('utf-8')
                        reference_images.append(img_base64)
                        print(f"   ✅ Downloaded and converted image to base64 ({len(img_base64)} chars)")
                    else:
                        print(f"   ⚠️  Failed to download image: {img_response.status_code}, skipping")
                except Exception as e:
                    print(f"   ⚠️  Error downloading image {ref_url[:50]}...: {str(e)[:100]}")
            elif isinstance(ref, str):
                # This is already a base64 string (extracted from data URL)
                reference_images.append(ref)
                print(f"   ✅ Using provided base64 image ({len(ref)} chars)")
            else:
                print(f"   ⚠️  Unknown reference format, skipping")
        
        if not reference_images:
            print(f"⚠️  No reference images available, skipping")
            return GeneratedImage(
                task_id="none",
                prompt=prompt,
                reference_image_url=reference_image_url,
                status="skipped",
                image_urls=[],
                error="No reference images available",
            )
        
        # Update prompt to mention all products if we have multiple references
        if len(reference_images) > 1:
            enhanced_prompt = f"{enhanced_prompt}\n\nIMPORTANT: This image must feature ALL {len(reference_images)} products from the reference images. Each product should be clearly visible and naturally integrated into the scene."
        
        # According to Freepik API docs, reference_images should be an array of base64 strings or URLs
        # We're sending base64 strings (without data URL prefix, just the base64 part)
        payload = {
            "prompt": enhanced_prompt,
            "reference_images": reference_images,  # Base64 encoded images (array of base64 strings)
        }
        
        print(f"   Payload: prompt length={len(enhanced_prompt)}, reference_images count={len(reference_images)}")
        print(f"   First reference image preview: {reference_images[0][:100] if reference_images else 'None'}...")
        
        print(f"   Using {len(reference_images)} product reference image(s) as base64 (one from each search)")
        
        try:
            # Call Freepik Nano Banana (Gemini 2.5 Flash) endpoint with Nano Banana product image from Qdrant
            print(f"   Calling Freepik Nano Banana (Gemini 2.5 Flash) API...")
            print(f"   Using Nano Banana product image from Qdrant: {reference_image_url[:60]}...")
            response = requests.post(
                "https://api.freepik.com/v1/ai/gemini-2-5-flash-image-preview",
                headers=headers,
                json=payload,
                timeout=15,
            )
            
            print(f"   Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   Response structure: {str(data)[:500]}")
                
                # Nano Banana (Gemini 2.5 Flash) returns task_id in data object
                task_data = data.get("data", {})
                task_id = task_data.get("task_id")
                status = task_data.get("status", "UNKNOWN")
                generated = task_data.get("generated", [])
                
                # Check for base64 in response (some endpoints return base64 directly)
                base64_data = task_data.get("base64", [])
                if not base64_data and "data" in data and isinstance(data["data"], list):
                    # Check if data array contains base64 objects
                    for item in data["data"]:
                        if isinstance(item, dict) and "base64" in item:
                            base64_data.append(item["base64"])
                
                print(f"   Task ID: {task_id}, Status: {status}")
                print(f"   Generated URLs: {len(generated) if isinstance(generated, list) else 0}")
                print(f"   Base64 images: {len(base64_data) if isinstance(base64_data, list) else 0}")
                if generated:
                    print(f"   First URL: {generated[0] if isinstance(generated, list) else generated[:100]}")
                
                if status == "COMPLETED":
                    # Check for base64 images first
                    base64_images = task_data.get("base64", [])
                    if base64_images:
                        # Convert base64 to data URLs
                        import base64 as b64
                        data_urls = []
                        for img_b64 in base64_images if isinstance(base64_images, list) else [base64_images]:
                            if isinstance(img_b64, dict):
                                img_b64 = img_b64.get("base64", "")
                            if img_b64:
                                data_urls.append(f"data:image/jpeg;base64,{img_b64}")
                        if data_urls:
                            print(f"   ✅ Image generated with base64 data ({len(data_urls)} images)")
                            return GeneratedImage(
                                task_id=task_id or "freepik-nano-banana-completed",
                                prompt=prompt,
                                reference_image_url=reference_image_url,
                                status="completed",
                                image_urls=data_urls,
                            )
                    
                    # Fall back to URL-based images
                    if generated:
                        print(f"   ✅ Image generated successfully with product!")
                        return GeneratedImage(
                            task_id=task_id or "freepik-nano-banana-completed",
                            prompt=prompt,
                            reference_image_url=reference_image_url,
                            status="completed",
                            image_urls=generated if isinstance(generated, list) else [generated],
                        )
                
                elif status in ["IN_PROGRESS", "CREATED", "PROCESSING"]:
                    # Poll for completion
                    print(f"   Task {task_id} {status.lower()}, polling (max 45s)...")
                    print(f"   Using Nano Banana product image: {reference_image_url[:60]}...")
                    result = self._poll_task_status(task_id, max_wait=45)  # Wait longer for generation
                    if result and result.get("status") == "completed":
                        image_urls = result.get("image_urls", [])
                        if image_urls:
                            print(f"   ✅ Image generated with Nano Banana product reference!")
                            return GeneratedImage(
                                task_id=task_id,
                                prompt=prompt,
                                reference_image_url=reference_image_url,
                                status="completed",
                                image_urls=image_urls,
                            )
                    
                    print(f"   ⚠️  Polling timeout or failed, using Nano Banana product image")
                    # Fallback: use Nano Banana product image directly
                    return GeneratedImage(
                        task_id="nano-banana-fallback-" + reference_image_url.split("/")[-1][:10],
                        prompt=prompt,
                        reference_image_url=reference_image_url,
                        status="completed",
                        image_urls=[reference_image_url],  # Nano Banana product image
                    )
                else:
                    print(f"   ⚠️  Unexpected status: {status}, using Nano Banana product image")
                    # Fallback: use Nano Banana product image directly
                    return GeneratedImage(
                        task_id="nano-banana-fallback-" + reference_image_url.split("/")[-1][:10],
                        prompt=prompt,
                        reference_image_url=reference_image_url,
                        status="completed",
                        image_urls=[reference_image_url],  # Nano Banana product image
                    )
            else:
                error_msg = response.text[:500]
                print(f"⚠️  Freepik API error: {response.status_code}")
                print(f"   Error details: {error_msg}")
                # Fallback: use product image directly
                print(f"   Falling back to using product image directly...")
                return GeneratedImage(
                    task_id="nano-banana-fallback-" + reference_image_url.split("/")[-1][:10],
                    prompt=prompt,
                    reference_image_url=reference_image_url,
                    status="completed",
                    image_urls=[reference_image_url],
                )
                
        except Exception as e:
            print(f"⚠️  Error calling Freepik API: {e}")
            # Fallback: use product image directly
            print(f"   Falling back to using product image directly...")
            return GeneratedImage(
                task_id="nano-banana-fallback-" + reference_image_url.split("/")[-1][:10],
                prompt=prompt,
                reference_image_url=reference_image_url,
                status="completed",
                image_urls=[reference_image_url],
            )
    
    def verify_generated_image(self, image_url: str, expected_product: str, prompt: str) -> dict[str, Any]:
        """
        Use Gemini vision to verify the generated image contains the expected product.
        
        Args:
            image_url: URL or data URL of the generated image
            expected_product: Product ID or description that should be in the image
            prompt: Original generation prompt for context
            
        Returns:
            Dictionary with verification results:
            - verified: bool - Whether product is visible
            - confidence: float - Confidence score (0-1)
            - details: str - Description of what was found
            - issues: list[str] - Any issues found
        """
        print(f"\n🔍 Verifying generated image with Gemini vision...")
        print(f"   Expected product: {expected_product}")
        
        try:
            # Download image if it's a URL
            image_data = None
            if image_url.startswith('data:'):
                # Extract base64 from data URL
                header, encoded = image_url.split(',', 1)
                image_data = base64.b64decode(encoded)
            elif image_url.startswith('http'):
                # Download image
                img_response = requests.get(image_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                if img_response.status_code == 200:
                    image_data = img_response.content
                else:
                    print(f"   ⚠️  Failed to download image for verification: {img_response.status_code}")
                    return {
                        "verified": False,
                        "confidence": 0.0,
                        "details": "Could not download image for verification",
                        "issues": ["Image download failed"]
                    }
            else:
                print(f"   ⚠️  Invalid image URL format")
                return {
                    "verified": False,
                    "confidence": 0.0,
                    "details": "Invalid image URL",
                    "issues": ["Invalid URL format"]
                }
            
            if not image_data:
                return {
                    "verified": False,
                    "confidence": 0.0,
                    "details": "No image data available",
                    "issues": ["No image data"]
                }
            
            # Use Gemini to analyze the image
            verification_prompt = f"""Analyze this generated advertisement image and verify:

1. Does the image contain the expected product? (Product ID/description: {expected_product})
2. Is the product clearly visible and prominent?
3. Does the image match the generation prompt: "{prompt[:200]}"
4. Is the composition realistic? (products on surfaces, not floating, proper shadows)
5. Is the text/copy visible and readable?

Return a JSON object with:
- "verified": true/false (product is visible and matches expectations)
- "confidence": 0.0-1.0 (how confident you are)
- "details": "Detailed description of what you see in the image"
- "issues": ["list", "of", "any", "issues", "found"] (empty array if none)

Be specific about what products, objects, or text you can see in the image."""
            
            # Create image part for Gemini
            image_part = {
                "mime_type": "image/jpeg" if not image_url.startswith('data:image/png') else "image/png",
                "data": base64.b64encode(image_data).decode('utf-8')
            }
            
            # Call Gemini with vision
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[image_part, verification_prompt],
                config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json"
                }
            )
            
            # Parse response
            result_text = response.text.strip()
            if result_text.startswith('```json'):
                result_text = result_text[7:-3].strip()
            elif result_text.startswith('```'):
                result_text = result_text[3:-3].strip()
            
            verification_result = json.loads(result_text)
            
            print(f"   ✅ Verification complete:")
            print(f"      Verified: {verification_result.get('verified', False)}")
            print(f"      Confidence: {verification_result.get('confidence', 0.0):.2f}")
            print(f"      Details: {verification_result.get('details', 'N/A')[:100]}...")
            
            return verification_result
            
        except Exception as e:
            print(f"   ⚠️  Error verifying image: {e}")
            import traceback
            traceback.print_exc()
            return {
                "verified": False,
                "confidence": 0.0,
                "details": f"Verification error: {str(e)}",
                "issues": [f"Verification failed: {str(e)}"]
            }
    
    def _poll_task_status(self, task_id: str, max_wait: int = 30) -> dict[str, Any] | None:
        """
        Poll Freepik task status until completion or timeout.
        
        Args:
            task_id: Freepik task ID
            max_wait: Maximum seconds to wait
            
        Returns:
            Result dictionary or None
        """
        headers = {
            "x-freepik-api-key": self.freepik_api_key,
        }
        
        endpoints = [
            f"https://api.freepik.com/v1/ai/gemini-2-5-flash-image-preview/{task_id}",
            f"https://api.freepik.com/v1/ai/tasks/{task_id}",
            f"https://api.freepik.com/v1/tasks/{task_id}",
        ]
        
        start_time = time.time()
        dots = 0
        
        while time.time() - start_time < max_wait:
            # Show progress
            dots = (dots + 1) % 4
            print(f"\r   Waiting for completion{'.' * dots}   ", end="", flush=True)
            
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, headers=headers, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        task_data = data.get("data", {})
                        status = task_data.get("status", task_data.get("task_status", "UNKNOWN"))
                        
                        if status in ["COMPLETED", "completed"]:
                            print()  # New line after dots
                            generated = task_data.get("generated", [])
                            # Handle both list and single URL formats
                            if isinstance(generated, str):
                                generated = [generated]
                            elif not isinstance(generated, list):
                                generated = []
                            
                            # Check if response contains base64 data directly
                            base64_images = task_data.get("base64", [])
                            if base64_images:
                                # Convert base64 to data URLs
                                import base64 as b64
                                data_urls = []
                                for img_b64 in base64_images if isinstance(base64_images, list) else [base64_images]:
                                    if isinstance(img_b64, dict):
                                        img_b64 = img_b64.get("base64", "")
                                    if img_b64:
                                        data_urls.append(f"data:image/jpeg;base64,{img_b64}")
                                if data_urls:
                                    print(f"   ✅ Found {len(data_urls)} base64 images in response")
                                    return {
                                        "status": "completed",
                                        "image_urls": data_urls,
                                    }
                            
                            return {
                                "status": "completed",
                                "image_urls": generated,
                            }
                        elif status in ["FAILED", "failed"]:
                            print()  # New line after dots
                            return {
                                "status": "failed",
                                "error": task_data.get("error", "Generation failed"),
                            }
                        
                        # Still processing, continue polling
                        break
                        
                except requests.exceptions.RequestException:
                    continue
            
            time.sleep(2)  # Check more frequently
        
        print()  # New line after dots
        return {"status": "timeout", "error": "Task did not complete in time"}
    
    def add_text_to_image(
        self,
        image_url: str,
        ad_copy: "AdCopy",
    ) -> str:
        """
        Add ad copy text overlay to the generated image.
        
        Args:
            image_url: URL of the generated image
            ad_copy: AdCopy object with headline, body, and CTA
            
        Returns:
            Base64 data URL of the image with text overlay
        """
        try:
            print(f"\n📝 Adding ad copy to image...")
            
            # Download image
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                print(f"   ⚠️  Could not download image, returning original")
                return image_url
            
            # Open image
            img = Image.open(io.BytesIO(response.content))
            img = img.convert('RGB')
            
            # Create a copy for drawing
            draw = ImageDraw.Draw(img)
            width, height = img.size
            
            # Try to load a nice font, fallback to default
            try:
                # Try to use a bold font
                font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(height * 0.08))
                font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(height * 0.05))
                font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(height * 0.04))
            except:
                try:
                    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(height * 0.08))
                    font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(height * 0.05))
                    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(height * 0.04))
                except:
                    # Fallback to default font
                    font_large = ImageFont.load_default()
                    font_medium = ImageFont.load_default()
                    font_small = ImageFont.load_default()
            
            # Add semi-transparent overlay for text readability
            overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            
            # Draw gradient overlay at bottom for text
            for y in range(height - int(height * 0.4), height):
                alpha = int(200 * (1 - (height - y) / (height * 0.4)))
                overlay_draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))
            
            img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
            draw = ImageDraw.Draw(img)
            
            # Calculate text positions
            y_start = int(height * 0.65)
            line_height_large = int(height * 0.1)
            line_height_medium = int(height * 0.06)
            line_height_small = int(height * 0.05)
            
            # Draw headline (top, bold, white)
            headline = ad_copy.headline
            bbox = draw.textbbox((0, 0), headline, font=font_large)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            y = y_start
            
            # Draw text with outline for readability
            for adj in range(-2, 3):
                for adj2 in range(-2, 3):
                    draw.text((x + adj, y + adj2), headline, font=font_large, fill=(0, 0, 0, 200))
            draw.text((x, y), headline, font=font_large, fill=(255, 255, 255))
            
            # Draw body text (middle, white)
            y += line_height_large + 10
            body_lines = ad_copy.body.split('. ')[:2]  # First 2 sentences
            body_text = '. '.join(body_lines)
            if len(body_text) > 80:
                body_text = body_text[:77] + "..."
            
            bbox = draw.textbbox((0, 0), body_text, font=font_medium)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2
            
            for adj in range(-1, 2):
                for adj2 in range(-1, 2):
                    draw.text((x + adj, y + adj2), body_text, font=font_medium, fill=(0, 0, 0, 200))
            draw.text((x, y), body_text, font=font_medium, fill=(255, 255, 255))
            
            # Draw CTA button (bottom, highlighted)
            y += line_height_medium + 20
            cta = ad_copy.call_to_action
            
            # Draw button background
            bbox = draw.textbbox((0, 0), cta, font=font_small)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[0]
            button_padding = 20
            button_x = (width - text_width - button_padding * 2) // 2
            button_y = y - 10
            
            draw.rectangle(
                [(button_x, button_y), (button_x + text_width + button_padding * 2, button_y + text_height + button_padding)],
                fill=(255, 255, 255),
                outline=(255, 255, 255),
                width=2
            )
            
            # Draw CTA text on button
            cta_x = button_x + button_padding
            draw.text((cta_x, button_y + button_padding // 2), cta, font=font_small, fill=(0, 0, 0))
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=95)
            img_bytes = buffer.getvalue()
            import base64
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{img_base64}"
            
            print(f"   ✅ Ad copy added to image")
            return data_url
            
        except Exception as e:
            print(f"   ⚠️  Error adding text to image: {e}")
            return image_url  # Return original if overlay fails
    
    def generate_ad_copy(
        self,
        query: str,
        products: list[Product],
        generated_images: list[GeneratedImage],
    ) -> AdCopy:
        """
        Generate compelling ad copy using Gemini.
        
        Args:
            query: Original search query
            products: List of Product objects
            generated_images: List of GeneratedImage objects
            
        Returns:
            AdCopy object
        """
        print(f"\n✍️  Step 4: Generating ad copy with Gemini...")
        print("-" * 70)
        
        # Prepare detailed product context with image URLs
        product_details = []
        for p in products[:5]:
            product_details.append(
                f"- Product ID: {p.product_id}\n"
                f"  Relevance Score: {p.score:.2%}\n"
                f"  Product Image: {p.image_url}"
            )
        product_summary = "\n".join(product_details)
        
        # Prepare detailed image context with URLs
        image_details = []
        for i, img in enumerate(generated_images, 1):
            if img.status == "completed":
                image_info = f"Image {i}:\n"
                image_info += f"  Prompt: {img.prompt}\n"
                if img.reference_image_url:
                    image_info += f"  Reference Product Image: {img.reference_image_url}\n"
                if img.image_urls:
                    image_info += f"  Generated Ad Image(s): {', '.join(img.image_urls[:3])}\n"
                image_details.append(image_info)
        
        image_summary = "\n".join(image_details) if image_details else "No images generated yet."
        
        prompt = f"""You are a world-class copywriter creating minimalist, clean advertisement copy.

Campaign Theme: "{query}"

PRODUCTS SELECTED:
{product_summary}

GENERATED AD IMAGES:
{image_summary}

Create minimalistic, clean advertisement copy following these principles:
1. **Headline**: Short, punchy, emotional hook (3-7 words max). No product codes. Focus on feeling, benefit, or aspiration.
2. **Body**: One powerful sentence (max 15 words). Capture the essence, not a description. Make it memorable and impactful.
3. **Call-to-action**: Ultra-short, action-oriented (2-4 words). Direct and compelling.

Rules:
- NO product codes or technical details
- NO long paragraphs or lists
- NO generic marketing speak
- YES to emotion, aspiration, and clarity
- YES to minimalism and impact
- Think Apple, Nike, Patagonia - clean, powerful, memorable

Return JSON with these exact keys:
- "headline": string (3-7 words, powerful and emotional)
- "body": string (one sentence, max 15 words, impactful)
- "call_to_action": string (2-4 words, action-oriented)
- "image_suggestions": string (brief note on image usage)

Example style:
- Headline: "Just Do It" or "Think Different" or "Find Your Adventure"
- Body: "Gear that moves with you." or "Built for the journey ahead."
- CTA: "Shop Now" or "Explore" or "Get Started"

Make it world-class, minimalistic, and clean."""

        try:
            # Use new SDK client
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
                contents=prompt
            )
            
            # Extract JSON from response (new SDK returns .text directly)
            response_text = response.text.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            ad_data = json.loads(response_text)
            
            ad_copy = AdCopy(
                headline=ad_data.get("headline", f"Discover {query}"),
                body=ad_data.get("body", f"Find the perfect items for {query}."),
                call_to_action=ad_data.get("call_to_action", "Shop Now"),
                image_suggestions=ad_data.get("image_suggestions", "Use all generated images"),
            )
            
            print(f"✓ Ad copy generated:")
            print(f"  Headline: {ad_copy.headline}")
            print(f"  CTA: {ad_copy.call_to_action}")
            
            return ad_copy
            
        except Exception as e:
            print(f"⚠️  Error generating ad copy: {e}")
            # Fallback
            return AdCopy(
                headline=f"Discover {query}",
                body=f"Find the perfect items for {query}. Our curated selection matches your style and needs.",
                call_to_action="Shop Now",
                image_suggestions="Use all generated images",
            )
    
    def save_ad_output(
        self,
        query: str,
        products: list[Product],
        generated_images: list[GeneratedImage],
        ad_copy: AdCopy,
        output_dir: Path,
    ) -> None:
        """
        Save the complete advertisement output.
        
        Args:
            query: Original search query
            products: List of Product objects
            generated_images: List of GeneratedImage objects
            ad_copy: AdCopy object
            output_dir: Output directory path
        """
        print(f"\n💾 Step 5: Saving advertisement output...")
        print("-" * 70)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON data
        ad_data = {
            "query": query,
            "ad_copy": {
                "headline": ad_copy.headline,
                "body": ad_copy.body,
                "call_to_action": ad_copy.call_to_action,
                "image_suggestions": ad_copy.image_suggestions,
            },
            "products": [
                {
                    "product_id": p.product_id,
                    "image_url": p.image_url,
                    "score": p.score,
                }
                for p in products
            ],
            "generated_images": [
                {
                    "task_id": img.task_id,
                    "prompt": img.prompt,
                    "reference_image_url": img.reference_image_url,
                    "status": img.status,
                    "image_urls": img.image_urls,
                    "error": img.error,
                }
                for img in generated_images
            ],
        }
        
        json_path = output_dir / "ad_data.json"
        with open(json_path, "w") as f:
            json.dump(ad_data, f, indent=2)
        print(f"✓ Saved ad data: {json_path}")
        
        # Download images
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        # Download product images
        for i, product in enumerate(products[:3], 1):
            if product.image_url and product.image_url != "N/A":
                img_path = images_dir / f"product_{i}_{product.product_id}.jpg"
                if self._download_image(product.image_url, img_path):
                    print(f"✓ Downloaded product image {i}")
        
        # Download generated images
        for i, img_data in enumerate(generated_images, 1):
            if img_data.status == "completed":
                for j, url in enumerate(img_data.image_urls, 1):
                    img_path = images_dir / f"generated_{i}_{j}.jpg"
                    if self._download_image(url, img_path):
                        print(f"✓ Downloaded generated image {i}-{j}")
        
        # Create HTML preview
        html_path = output_dir / "ad_preview.html"
        self._create_html_preview(query, ad_copy, products, generated_images, html_path)
        print(f"✓ Created HTML preview: {html_path}")
        
        print(f"\n✅ Advertisement saved to: {output_dir}")
        print(f"   Open {html_path} in your browser to view the ad")
    
    def _download_image(self, url: str, save_path: Path) -> bool:
        """Download an image from URL."""
        try:
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception:
            return False
    
    def _create_html_preview(
        self,
        query: str,
        ad_copy: AdCopy,
        products: list[Product],
        generated_images: list[GeneratedImage],
        html_path: Path,
    ) -> None:
        """Create an HTML preview of the advertisement."""
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ad: {query}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1000px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .headline {{
            font-size: 48px;
            font-weight: bold;
            color: #1a1a1a;
            margin-bottom: 20px;
            line-height: 1.2;
        }}
        .body {{
            font-size: 20px;
            line-height: 1.6;
            color: #666;
            margin-bottom: 30px;
        }}
        .cta {{
            display: inline-block;
            background: #007bff;
            color: white;
            padding: 16px 40px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 20px;
            transition: background 0.3s;
        }}
        .cta:hover {{
            background: #0056b3;
        }}
        .section {{
            margin-top: 50px;
            padding-top: 30px;
            border-top: 1px solid #e0e0e0;
        }}
        .section h2 {{
            color: #333;
            margin-bottom: 20px;
        }}
        .images {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .image {{
            width: 100%;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .meta {{
            font-size: 14px;
            color: #999;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1 class="headline">{ad_copy.headline}</h1>
        <p class="body">{ad_copy.body}</p>
        <a href="#" class="cta">{ad_copy.call_to_action}</a>
        
        <div class="section">
            <h2>Generated Ad Images</h2>
            <div class="images">
"""
        
        # Add generated images
        for i, img_data in enumerate(generated_images, 1):
            if img_data.status == "completed":
                for j in range(len(img_data.image_urls)):
                    html_content += f'                <img src="images/generated_{i}_{j+1}.jpg" class="image" alt="Generated ad image">\n'
        
        html_content += """            </div>
        </div>
        
        <div class="section">
            <h2>Product References</h2>
            <div class="images">
"""
        
        # Add product images
        for i, product in enumerate(products[:3], 1):
            if product.image_url != "N/A":
                html_content += f'                <img src="images/product_{i}_{product.product_id}.jpg" class="image" alt="Product {product.product_id}">\n'
        
        html_content += f"""            </div>
        </div>
        
        <div class="meta">
            Campaign Query: {query}<br>
            Generated by Ad Generation Agent
        </div>
    </div>
</body>
</html>"""
        
        with open(html_path, "w") as f:
            f.write(html_content)
    
    def create_ad(
        self,
        query: str,
        num_products: int = 5,
        num_images: int = 2,
        output_dir: Path = Path("./ads"),
    ) -> None:
        """
        Complete workflow to create an advertisement.
        
        Args:
            query: Search query/campaign theme
            num_products: Number of products to search for
            num_images: Number of images to generate
            output_dir: Output directory for ad files
        """
        print("=" * 70)
        print(f"🚀 AD GENERATION WORKFLOW")
        print(f"Query: {query}")
        print("=" * 70)
        
        # Step 1: Search for products
        products = self.search_products(query, limit=num_products)
        if not products:
            print("❌ No products found. Cannot create ad.")
            return
        
        # Step 2: Generate image prompts
        image_prompts = self.generate_image_prompts(query, products, num_prompts=num_images)
        
        # Step 3: Generate images with Freepik
        print(f"\n🎨 Step 3: Generating {len(image_prompts)} images with Freepik...")
        print("-" * 70)
        
        generated_images = []
        for i, prompt_data in enumerate(image_prompts, 1):
            print(f"\n[Image {i}/{len(image_prompts)}]")
            
            prompt = prompt_data.get("prompt", "")
            product_ref = prompt_data.get("product_reference", "none")
            
            # Find reference image URL
            reference_url = None
            if product_ref != "none":
                for product in products:
                    if product.product_id == product_ref:
                        reference_url = product.image_url
                        break
            
            # Generate image
            result = self.generate_image_with_freepik(prompt, reference_url)
            if result:
                generated_images.append(result)
        
        if not generated_images:
            print("⚠️  No images were generated. Continuing with ad copy only...")
        
        # Step 4: Generate ad copy
        ad_copy = self.generate_ad_copy(query, products, generated_images)
        
        # Step 5: Save output
        self.save_ad_output(query, products, generated_images, ad_copy, output_dir)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ad Generation Agent - Create advertisements from queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent.py "beach vacation essentials"
  python agent.py "weekend mountain adventure" --num-products 3 --num-images 1
  python agent.py "minimalist home office" --output ./my-ads
        """,
    )
    
    parser.add_argument(
        "query",
        type=str,
        help="Search query / campaign theme",
    )
    parser.add_argument(
        "--num-products",
        type=int,
        default=5,
        help="Number of products to search for (default: 5)",
    )
    parser.add_argument(
        "--num-images",
        type=int,
        default=2,
        help="Number of images to generate (default: 2)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./ads"),
        help="Output directory (default: ./ads)",
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", "shopping-queries-images"),
        help="Qdrant collection name",
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get required environment variables
    required_vars = {
        "QDRANT_URL": os.getenv("QDRANT_URL"),
        "QDRANT_API_KEY": os.getenv("QDRANT_API_KEY"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "FREEPIK_API_KEY": os.getenv("FREEPIK_API_KEY"),
    }
    
    # Check for missing variables
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("Please set them in your .env file")
        return
    
    # Initialize agent
    agent = AdGenerationAgent(
        qdrant_url=required_vars["QDRANT_URL"],
        qdrant_api_key=required_vars["QDRANT_API_KEY"],
        gemini_api_key=required_vars["GEMINI_API_KEY"],
        freepik_api_key=required_vars["FREEPIK_API_KEY"],
        collection_name=args.collection,
    )
    
    # Create ad
    agent.create_ad(
        query=args.query,
        num_products=args.num_products,
        num_images=args.num_images,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()

