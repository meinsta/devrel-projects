#!/bin/bash
# Setup script for Ad Generation Agent

set -e  # Exit on error

echo "=================================="
echo "🚀 Ad Generation Agent - Setup"
echo "=================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $python_version"

# Check Node.js version
echo ""
echo "Checking Node.js version..."
node_version=$(node --version 2>&1)
echo "✓ Node.js $node_version"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
if command -v uv &> /dev/null; then
    echo "Using uv for faster installation..."
    echo "Using uv for faster installation..."
    uv pip install -r requirements.txt
else
    echo "Using pip..."
    pip3 install -r requirements.txt
fi
echo "✓ Python dependencies installed"

# Install frontend dependencies
echo ""
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..
echo "✓ Frontend dependencies installed"

# Check for .env file
echo ""
if [ -f .env ]; then
    echo "✓ .env file found"
else
    echo "⚠️  .env file not found"
    echo ""
    echo "Creating .env template..."
    cat > .env << 'EOF'
# Qdrant Configuration
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key
QDRANT_COLLECTION=shopping-queries-images

# AI Model APIs
GEMINI_API_KEY=your_gemini_api_key
FREEPIK_API_KEY=your_freepik_api_key

# Optional: Model Configuration
FREEPIK_MODEL=flux-1-1-pro
TEXT_EMBEDDING_MODEL=Qdrant/clip-ViT-B-32-text
EOF
    echo "✓ Created .env template"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your API keys before running!"
fi

# Run verification
echo ""
echo "Running setup verification..."
python3 scripts/verify_setup.py || true

echo ""
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys (if not done already)"
echo "2. Start the agent:"
echo "   ./start_agent.sh"
echo ""
echo "   Or manually:"
echo "   python3 api.py"
echo "   cd frontend && npm run dev"
echo ""
echo "4. Open http://localhost:3001 in your browser"
echo ""
echo "For more details, see SETUP.md"



