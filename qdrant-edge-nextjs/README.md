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

# Put your input video where BOTH halves read it: the API indexes public/video.mp4,
# the Next.js page plays frontend/public/video.mp4
cp my-video.mp4 public/video.mp4
cp my-video.mp4 frontend/public/video.mp4

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

## Notes

- The API reads `public/video.mp4` (repo root); the frontend serves `frontend/public/video.mp4`. Keep both
  in sync, or set `NEXT_PUBLIC_VIDEO_URL` to a hosted copy of the same file.
- The frontend's `NEXT_PUBLIC_API_URL` (default `http://localhost:7777`) is called from the visitor's
  browser, so a hosted frontend needs a publicly reachable API.
