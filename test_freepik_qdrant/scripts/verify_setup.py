#!/usr/bin/env python3
"""
Quick Setup Verification for H&M Ad Agent
=========================================
Checks that everything is configured correctly.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def check_env_file():
    """Check if .env file exists and has required variables."""
    env_path = Path(".env")
    
    if not env_path.exists():
        print("❌ .env file not found")
        print("📝 Please create .env file with the following variables:")
        print("")
        with open(".env.template", "r") as f:
            print(f.read())
        return False
    
    print("✅ .env file found")
    load_dotenv()
    
    required_vars = {
        "QDRANT_URL": "Qdrant cluster URL",
        "QDRANT_API_KEY": "Qdrant API key",
        "GEMINI_API_KEY": "Google Gemini API key",
        "FREEPIK_API_KEY": "Freepik API key",
    }
    
    missing = []
    for var, desc in required_vars.items():
        value = os.getenv(var) or os.getenv(var.replace("GEMINI", "GOOGLE"))
        if not value or value.startswith("your_"):
            missing.append(f"  - {var}: {desc}")
        else:
            print(f"✅ {var} is set")
    
    if missing:
        print("\n❌ Missing or placeholder values:")
        for m in missing:
            print(m)
        return False
    
    return True


def check_dataset():
    """Check if H&M dataset is downloaded."""
    dataset_path = Path("hm_dataset.csv")
    
    if not dataset_path.exists():
        print("❌ H&M dataset not found")
        print("📥 Run this command to download:")
        print('   curl -L "https://raw.githubusercontent.com/luminati-io/HM-dataset-sample/main/H%26M-dataset-sample.csv" -o hm_dataset.csv')
        return False
    
    print(f"✅ H&M dataset found ({dataset_path.stat().st_size / 1024:.1f} KB)")
    return True


def check_dependencies():
    """Check if Python dependencies are installed."""
    try:
        import qdrant_client
        import fastembed
        import google.genai
        import fastapi
        print("✅ Python dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing Python dependencies: {e}")
        print("📦 Run: pip install -r requirements.txt")
        return False


def check_collection():
    """Check if Qdrant collection exists."""
    load_dotenv()
    
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    
    if not qdrant_url or not qdrant_api_key or qdrant_url.startswith("your_"):
        print("⚠️  Cannot check collection: Qdrant credentials not set")
        return False
    
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        
        collection_name = os.getenv("QDRANT_COLLECTION", "hm-products")
        
        try:
            info = client.get_collection(collection_name)
            print(f"✅ Qdrant collection '{collection_name}' exists ({info.points_count} products)")
            return True
        except Exception:
            print(f"❌ Collection '{collection_name}' not found")
            print(f"📥 Run: python3 scripts/ingest_hm_data.py hm_dataset.csv")
            return False
    
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant: {e}")
        return False


def check_frontend():
    """Check if frontend dependencies are installed."""
    node_modules = Path("frontend/node_modules")
    
    if not node_modules.exists():
        print("❌ Frontend dependencies not installed")
        print("📦 Run: cd frontend && npm install")
        return False
    
    print("✅ Frontend dependencies installed")
    return True


def main():
    print("🔍 H&M Ad Generation Agent - Setup Verification")
    print("=" * 60)
    print()
    
    checks = [
        ("Environment Variables", check_env_file),
        ("H&M Dataset", check_dataset),
        ("Python Dependencies", check_dependencies),
        ("Qdrant Collection", check_collection),
        ("Frontend Dependencies", check_frontend),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{'─' * 60}")
        print(f"Checking: {name}")
        print(f"{'─' * 60}")
        result = check_func()
        results.append(result)
    
    print(f"\n{'=' * 60}")
    if all(results):
        print("🎉 All checks passed! You're ready to run the agent.")
        print()
        print("Next steps:")
        print("  1. Run: ./start_agent.sh")
        print("  2. Open: http://localhost:3001")
        print(f"{'=' * 60}")
        sys.exit(0)
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        print(f"{'=' * 60}")
        sys.exit(1)


if __name__ == "__main__":
    main()
