#!/usr/bin/env python3
"""Test if Gemini actually generates ad copy or falls back"""
import os
from dotenv import load_dotenv
from google import genai
import json

load_dotenv()

key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
print("=" * 70)
print("Testing Gemini Ad Copy Generation")
print("=" * 70)
print(f"\nAPI Key: {key[:15]}...{key[-5:] if key else 'None'}")

client = genai.Client(api_key=key)

# Test the exact prompt we use in the agent
prompt = """You are a professional copywriter creating an advertisement.

Campaign Theme: "hiking adventure gear"

Products Selected:
- Product B07JZ6XCQM (relevance: 0.3204)
- Product B07G8CQGLK (relevance: 0.3199)
- Product B0922H491B (relevance: 0.3196)

Generated Visuals:
- Professional product photography for hiking adventure gear...

Create compelling advertisement copy with:
1. A powerful, attention-grabbing headline (max 10 words)
2. Engaging body copy (2-3 sentences, focus on benefits and emotion)
3. A clear, action-oriented call-to-action (max 5 words)
4. Brief suggestion on which images work best with the copy

Return JSON with these exact keys:
- "headline": string
- "body": string
- "call_to_action": string
- "image_suggestions": string

Make it persuasive, energetic, and aligned with the campaign theme."""

print("\n" + "=" * 70)
print("Calling Gemini API...")
print("=" * 70)

try:
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=prompt
    )
    
    print("\n✅ GEMINI API SUCCESS!")
    print("\nRaw Response:")
    print("-" * 70)
    print(response.text)
    print("-" * 70)
    
    # Try to parse JSON
    response_text = response.text.strip()
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    try:
        ad_data = json.loads(response_text)
        print("\n✅ Parsed JSON Successfully:")
        print(f"  Headline: {ad_data.get('headline', 'N/A')}")
        print(f"  Body: {ad_data.get('body', 'N/A')[:100]}...")
        print(f"  CTA: {ad_data.get('call_to_action', 'N/A')}")
        print("\n🎉 GEMINI IS WORKING - Real ad copy generated!")
    except json.JSONDecodeError as e:
        print(f"\n⚠️  JSON parse error: {e}")
        print("But Gemini responded with text!")
        
except Exception as e:
    error_str = str(e)
    print(f"\n❌ GEMINI API FAILED")
    print("-" * 70)
    
    if "404" in error_str:
        print("Error: Model not found")
        print(f"Details: {error_str[:200]}")
        print("\n⚠️  FALLBACK WILL BE USED")
    elif "429" in error_str or "quota" in error_str.lower():
        print("Error: Quota exceeded")
        print(f"Details: {error_str[:200]}")
        print("\n⚠️  FALLBACK WILL BE USED")
    elif "API key" in error_str or "INVALID" in error_str:
        print("Error: API key invalid")
        print(f"Details: {error_str[:200]}")
        print("\n⚠️  FALLBACK WILL BE USED")
    else:
        print(f"Error: {error_str[:200]}")
        print("\n⚠️  FALLBACK WILL BE USED")
    
    print("\n" + "=" * 70)
    print("FALLBACK COPY (what you get when Gemini fails):")
    print("=" * 70)
    print('  Headline: "Discover hiking adventure gear"')
    print('  Body: "Find the perfect items for hiking adventure gear. Our curated selection matches your style and needs."')
    print('  CTA: "Shop Now"')

