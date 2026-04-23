.PHONY: setup setup-api setup-frontend dev dev-api dev-frontend clean

# Setup everything
setup: setup-api setup-frontend
	@echo ""
	@echo "Setup complete! Run: make dev"

# Setup API (Python/FastAPI)
setup-api:
	@command -v uv >/dev/null || (echo "uv not installed." && exit 1)
	@echo "Installing API dependencies..."
	@cd api && uv sync --no-build-isolation
	@echo "Downloading CLIP models..."
	@cd api && uv run python -c "from fastembed import ImageEmbedding; ImageEmbedding(model_name='Qdrant/clip-ViT-B-32-vision')"
	@echo "Vision model ready"
	@cd api && uv run python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='Qdrant/clip-ViT-B-32-text')"
	@echo "Text model ready"

# Setup Frontend (Next.js)
setup-frontend:
	@command -v pnpm >/dev/null || (echo "pnpm not installed." && exit 1)
	@echo "Installing frontend dependencies..."
	@cd frontend && pnpm install

# Run everything in dev mode (requires two terminals or use & for background)
dev:
	@echo "Starting Qdrant Edge Visual Search Demo..."
	@echo ""
	@echo "API:      http://localhost:7777"
	@echo "Frontend: http://localhost:4321"
	@echo ""
	@make dev-api & make dev-frontend

# Run API only
dev-api:
	@cd api && uv run uvicorn main:app --host 0.0.0.0 --port 7777 --reload

# Run Frontend only
dev-frontend:
	@cd frontend && pnpm dev --port 4321

# Clean up
clean:
	rm -rf data api/.venv frontend/.next frontend/node_modules
