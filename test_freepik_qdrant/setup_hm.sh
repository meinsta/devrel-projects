#!/bin/bash
# Setup H&M Dataset for Ad Generation
# ===================================
# This script ingests the H&M product dataset into Qdrant

set -e

echo "🎨 H&M Ad Generation Agent - Dataset Setup"
echo "=========================================="
echo ""

# Check for .env file
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "Please create a .env file with:"
    echo "  QDRANT_URL=your_qdrant_url"
    echo "  QDRANT_API_KEY=your_api_key"
    echo "  GEMINI_API_KEY=your_gemini_key"
    echo "  FREEPIK_API_KEY=your_freepik_key"
    exit 1
fi

# Check if CSV exists
if [ ! -f "hm_dataset.csv" ]; then
    echo "📥 Downloading H&M dataset..."
    curl -L "https://raw.githubusercontent.com/luminati-io/HM-dataset-sample/main/H%26M-dataset-sample.csv" -o hm_dataset.csv
    echo "✅ Dataset downloaded"
else
    echo "✅ H&M dataset already downloaded"
fi

# Check Python dependencies
echo ""
echo "📦 Checking Python dependencies..."
if ! python3 -c "import qdrant_client" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Ingest data
echo ""
echo "🚀 Ingesting H&M products into Qdrant..."
echo "   Collection: hm-products"
echo "   Products: ~1000"
echo ""

python3 scripts/ingest_hm_data.py hm_dataset.csv \
    --collection hm-products \
    --batch-size 16 \
    --download-workers 8

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Update .env to set QDRANT_COLLECTION=hm-products"
echo "  2. Run: ./start_agent.sh"
echo "  3. Open: http://localhost:3001"
