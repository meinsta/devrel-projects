#!/bin/bash

# Quick demo runner script
# Usage: ./run_demo.sh [state] [num_questions]

set -e

# Default values
STATE=${1:-wyoming}
LIMIT=${2:-5}

echo "╔════════════════════════════════════════════════╗"
echo "║   Agentic Vector Search Demo                  ║"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "State: $STATE"
echo "Questions: $LIMIT"
echo ""

# Get repository root (two levels up from scripts/)
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Check if .env exists
if [ ! -f "$REPO_ROOT/.env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create a .env file in the repository root with your API keys."
    echo "See .env.example for template."
    exit 1
fi

# Check if dependencies are installed
if ! python -c "import crewai" 2>/dev/null; then
    echo "⚠️  Dependencies not installed. Installing now..."
    pip install -r "$REPO_ROOT/requirements.txt"
fi

echo "🚀 Running comparison demo..."
echo ""

# Run the comparison demo
python compare_vanilla_vs_agentic.py --state "$STATE" --limit "$LIMIT"

echo ""
echo "✅ Demo complete!"
echo ""
echo "Next steps:"
echo "  • Try a different state: ./run_demo.sh idaho 5"
echo "  • Run vanilla only: python $REPO_ROOT/examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 10"
echo "  • Run agentic only: python $REPO_ROOT/examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 10"
echo ""

