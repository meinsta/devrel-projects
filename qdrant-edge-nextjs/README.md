# Qdrant Edge Visual Search Demo

Real-time visual search powered by [Qdrant Edge](https://qdrant.tech/edge/) and CLIP embeddings.

This demo showcases how Qdrant Edge enables instant local vector search while seamlessly syncing to a Qdrant server in the background.

## Architecture

- **Frontend**: Next.js with Tailwind CSS
- **Backend**: FastAPI with Qdrant Edge
- **Embeddings**: CLIP (ViT-B-32) via FastEmbed
- **Vector DB**: Qdrant Edge (local) + Qdrant Server (cloud sync)

## Features

- Real-time video frame indexing
- Text-to-image semantic search
- Local-first search with instant results
- Background sync to Qdrant server
- Live status dashboard

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [pnpm](https://pnpm.io/installation)
- [Docker](https://docs.docker.com/engine/install/)

## Usage

```bash
# Start Qdrant server
docker run -d -p 6333:6333 qdrant/qdrant

# Setup (install deps + download models)
make setup

# Run the demo
make dev
```

Then open http://localhost:4321

## How It Works

1. Video frames are extracted at 1 FPS
2. Each frame is embedded using CLIP vision encoder
3. Embeddings are stored in local Qdrant Edge shard (instant)
4. Background worker syncs to Qdrant server
5. Search queries use CLIP text encoder
6. MMR (Maximal Marginal Relevance) returns diverse results
