# Cortex

**Persistent memory for coding agents.**

An MCP server that gives Claude Code (and other AI coding assistants) durable, queryable memory across sessions - backed by Qdrant.

## Philosophy

Agents should remember what worked. Cortex stores three types of memories:

- **Episodes** - What happened: errors hit, solutions found, commands run
- **Facts** - Stable knowledge: conventions, constraints, architecture decisions
- **Recipes** - How-to instructions: build steps, deploy procedures, test patterns

## Quick Start

```bash
# 1. Start Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# 2. Add to Claude Code
claude mcp add cortex \
  --env QDRANT_URL="http://localhost:6333" \
  -- uvx cortex-mcp start-mcp-server

# 3. Start using memory
remember(kind="fact", text="This project uses pytest for testing")
recall(query="testing")
```

## Tools

| Tool | Purpose | Example |
|------|---------|---------|
| `remember(kind, text)` | Store a memory | `remember("episode", "Fixed auth bug by checking token expiry")` |
| `recall(query)` | Search memories | `recall("authentication issues")` |
| `list_recent()` | Show recent memories | `list_recent(kind="episode", limit=10)` |
| `delete(id)` | Remove a memory | `delete("abc-123")` |
| `doctor()` | Diagnose issues | `doctor()` |

## Memory Contract

**Before acting:** Recall relevant context
```python
recall(query="<what you're about to do>")
```

**After completing:** Store what you learned
```python
# Bug fixed?
remember(kind="episode", text="Fixed X by doing Y", tags=["bugfix"])

# Learned a convention?
remember(kind="fact", text="This project uses snake_case for functions")

# Established a procedure?
remember(kind="recipe", text="To deploy: run `make deploy`", tags=["deploy"])
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `QDRANT_URL` | Qdrant server URL | Required |
| `QDRANT_API_KEY` | API key for Qdrant Cloud | Optional |

### Project Config (`cortex.toml`)

```toml
[memory]
default_episode_ttl_days = 90
default_fact_ttl_days = 365
default_recipe_ttl_days = 180

[security]
max_payload_bytes = 8192
block_secrets = true

[ranking]
freshness_decay_days = 30
verified_boost = 1.5
```

## Team Setup

Commit `.mcp.json` to share with your team:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "uvx",
      "args": ["cortex-mcp", "start-mcp-server"],
      "env": {
        "QDRANT_URL": "${QDRANT_URL}",
        "QDRANT_API_KEY": "${QDRANT_API_KEY}"
      }
    }
  }
}
```

## Safety

Cortex automatically blocks:
- API keys and tokens
- Private keys
- Database credentials
- Config dumps

Set `security.block_secrets = false` in `cortex.toml` to override (not recommended).

## Requirements

- Python 3.11+
- Qdrant 1.12+

## License

MIT
