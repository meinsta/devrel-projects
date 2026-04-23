#!/bin/bash
# Quick start script for Ad Generation Agent

echo "=================================="
echo "🚀 Starting Ad Generation Agent"
echo "=================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo ""
    echo "Please create a .env file with your API keys:"
    echo "  cp .env.example .env"
    echo "  # Edit .env with your keys"
    echo ""
    exit 1
fi

echo "Starting API backend on port 8001..."
echo "API will be available at: http://localhost:8001"
echo "API Docs: http://localhost:8001/docs"
echo ""

# Start API in background
python3 api.py &
API_PID=$!

# Wait for API to start
sleep 3

echo ""
echo "Starting frontend on port 3001..."
echo "Web interface: http://localhost:3001"
echo ""

# Start frontend
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=================================="
echo "✅ Agent is running!"
echo "=================================="
echo ""
echo "API:      http://localhost:8001"
echo "Frontend: http://localhost:3001"
echo ""
echo "Press Ctrl+C to stop all services"
echo "=================================="

# Wait for Ctrl+C
trap "kill $API_PID $FRONTEND_PID; exit" INT
wait



