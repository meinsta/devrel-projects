# Cortex - Long-term memory for coding agents
FROM python:3.11-slim

# Install system dependencies for LSP servers
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    # For Node.js LSPs (TypeScript, JavaScript)
    nodejs \
    npm \
    # For Rust LSP
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install uv

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system -e .

# Create non-root user
RUN useradd -m -s /bin/bash cortex
USER cortex

# Default environment
ENV QDRANT_URL=""
ENV QDRANT_API_KEY=""

# Expose nothing (MCP uses stdio)
# The server is invoked via stdin/stdout

# Default command - start MCP server
ENTRYPOINT ["cortex"]
CMD ["start-mcp-server", "--context", "claude-code"]
