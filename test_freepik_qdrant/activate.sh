#!/bin/bash
# Activate Virtual Environment Helper
# Usage: source activate.sh

if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated (Python $(python --version))"
    echo "📦 Ready to run agent commands"
    echo ""
    echo "Try:"
    echo "  python api.py                    # Start backend API"
    echo "  python agent.py \"your query\"     # Run agent CLI"
    echo "  ./start_agent.sh                 # Start full application"
    echo "  python scripts/verify_setup.py   # Verify setup"
else
    echo "❌ Virtual environment not found"
    echo "Run: python3.11 -m venv venv"
fi
