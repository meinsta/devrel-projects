"""Quick test to diagnose where the comparison script hangs."""

import os
import sys
from dotenv import load_dotenv

print("1. Loading environment...")
load_dotenv()

print("2. Checking API keys...")
openai_key = os.getenv('OPENAI_API_KEY')
qdrant_url = os.getenv('QDRANT_CLOUD_URL')
qdrant_key = os.getenv('QDRANT_API_KEY')

print(f"   OpenAI: {'✓' if openai_key else '✗'}")
print(f"   Qdrant URL: {'✓' if qdrant_url else '✗'}")
print(f"   Qdrant Key: {'✓' if qdrant_key else '✗'}")

print("\n3. Testing imports...")
try:
    from datasets import load_dataset
    print("   ✓ datasets")
except Exception as e:
    print(f"   ✗ datasets: {e}")

try:
    from qdrant_client import QdrantClient
    print("   ✓ qdrant_client")
except Exception as e:
    print(f"   ✗ qdrant_client: {e}")

try:
    from fastembed import TextEmbedding
    print("   ✓ fastembed")
except Exception as e:
    print(f"   ✗ fastembed: {e}")

try:
    from openai import OpenAI
    print("   ✓ openai")
except Exception as e:
    print(f"   ✗ openai: {e}")

try:
    from crewai import Agent, Task, Crew
    print("   ✓ crewai")
except Exception as e:
    print(f"   ✗ crewai: {e}")

print("\n4. Testing custom tool import...")
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'examples', '3_agentic_rag', 'tools'))
    from qdrant_tool import CustomQdrantTool
    print("   ✓ CustomQdrantTool imported successfully")
except Exception as e:
    print(f"   ✗ CustomQdrantTool: {e}")
    import traceback
    traceback.print_exc()

print("\n5. Testing Qdrant connection...")
if qdrant_url and qdrant_key:
    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
        collections = client.get_collections()
        print(f"   ✓ Connected! Found {len(collections.collections)} collections")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
else:
    print("   ⚠ Skipped (missing credentials)")

print("\n6. Testing dataset load...")
try:
    print("   Loading HousingQA dataset (this may take a moment)...")
    dataset = load_dataset("reglab/housing_qa", "questions", split="test[:1]", trust_remote_code=True)
    print(f"   ✓ Dataset loaded! Sample size: {len(dataset)}")
except Exception as e:
    print(f"   ✗ Dataset load failed: {e}")

print("\n✅ Diagnostic complete!")
print("\nIf everything passed, the issue is likely in the agent execution.")
print("Try running with verbose=True to see what the agents are doing.")

