#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_NAME="${SERVER_NAME:-qdrant-cloud-memory}"
COLLECTION_NAME="${COLLECTION_NAME:-codex-memory}"
EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-fastembed}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"

if codex mcp get "$SERVER_NAME" --json >/dev/null 2>&1; then
  echo "Codex MCP server '$SERVER_NAME' is already registered."
  echo "Remove it first if you want to recreate it:"
  echo "  codex mcp remove $SERVER_NAME"
  exit 0
fi

if [[ -z "${QDRANT_URL:-}" || -z "${QDRANT_API_KEY:-}" ]]; then
  if [[ -n "${QDRANT_CLUSTER_ID:-}" ]]; then
    eval "$("$ROOT/scripts/bootstrap_qdrant_cloud_env.py")"
  else
    echo "Set QDRANT_URL and QDRANT_API_KEY, or set QDRANT_CLUSTER_ID with qcloud configured." >&2
    exit 1
  fi
fi

codex mcp add "$SERVER_NAME" \
  --env "QDRANT_URL=$QDRANT_URL" \
  --env "QDRANT_API_KEY=$QDRANT_API_KEY" \
  --env "COLLECTION_NAME=$COLLECTION_NAME" \
  --env "EMBEDDING_PROVIDER=$EMBEDDING_PROVIDER" \
  --env "EMBEDDING_MODEL=$EMBEDDING_MODEL" \
  -- \
  uvx mcp-server-qdrant

echo "Registered Codex MCP server '$SERVER_NAME'."
echo "Inspect it with: codex mcp get $SERVER_NAME --json"
