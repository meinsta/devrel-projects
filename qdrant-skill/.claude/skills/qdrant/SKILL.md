---
name: qdrant
description: Expert guidance for Qdrant vector database development. Use when working with vector search, embeddings, similarity search, Qdrant collections, points, payloads, filtering, Qdrant Cloud, clusters, API keys, or any Qdrant client library (Python, JavaScript/TypeScript, Rust, Go, Java, .NET/C#). Covers client setup, collection management, vector indexing, search operations, and cloud deployment.
---

# Qdrant Vector Database Skill

This skill provides comprehensive guidance for developing with Qdrant vector database, with integrated MCP tools for accessing up-to-date code examples and documentation.

## MCP Code Snippets Requirement

**IMPORTANT**: This skill works best with the `mcp-code-snippets` MCP server for accurate, up-to-date code examples.

### Before Answering Qdrant Questions

1. **Always search first** using MCP tools (if available):
   - `mcp__mcp-code-snippets__lookup-snippet` - Search for Qdrant code examples and patterns

2. **If MCP tools are unavailable**:
   - Guide user to install: `pip install mcp-code-snippets`
   - Configure in their MCP client (see [Setup Guide](#mcp-setup))
   - Fall back to reference documentation in this skill

### MCP Setup

To enable dynamic code snippet lookup:

```bash
# Install mcp-code-snippets
pip install mcp-code-snippets
```

**Claude Code configuration:**
```bash
claude mcp add qdrant-snippets -- mcp-code-snippets
```

**Cursor/VS Code MCP configuration:**
```json
{
  "mcpServers": {
    "mcp-code-snippets": {
      "command": "mcp-code-snippets"
    }
  }
}
```

The MCP server auto-detects your project language and dependencies, then queries Qdrant's hosted code snippet database at `mcp.qdrant.tech`.

## When to Use This Skill

Use this skill when:
- Setting up Qdrant client connections (local or cloud)
- Creating and configuring collections
- Indexing vectors with payloads
- Performing similarity search or hybrid search
- Implementing filtering on payloads
- Optimizing performance (quantization, sharding, indexing)
- Deploying to Qdrant Cloud
- Troubleshooting Qdrant issues

## General Workflow

### Step 1: Understand the Task

Clarify with the user:
- Which Qdrant client language? (Python, JS/TS, Rust, Go, Java, .NET)
- Local Qdrant or Qdrant Cloud?
- What's the use case? (semantic search, RAG, recommendations, etc.)
- Scale expectations? (number of vectors, query throughput)

### Step 2: Search for Code Examples

Use MCP to find relevant examples:

```
# Example queries to lookup-snippet:
- "create collection with cosine distance"
- "upsert points with payload"
- "search with filter"
- "hybrid search sparse dense"
- "connect to qdrant cloud"
```

### Step 3: Provide Working Code

Always include:
- Complete, runnable code examples
- Proper error handling
- Comments explaining key concepts
- Environment variable usage for credentials (never hardcode API keys)

### Step 4: Verify Best Practices

Cross-reference with skill documentation:
- See `references/clients.md` for client-specific patterns
- See `references/cloud.md` for cloud deployment
- See `references/concepts.md` for architecture decisions
- See `references/examples.md` for common patterns

## Quick Reference

### Client Libraries

| Language | Package | Connection |
|----------|---------|------------|
| **Python** | `qdrant-client` | `QdrantClient(url, api_key)` |
| **JavaScript** | `@qdrant/js-client-rest` | `new QdrantClient({url, apiKey})` |
| **Rust** | `qdrant-client` | `Qdrant::from_url(url).api_key(key)` |
| **Go** | `github.com/qdrant/go-client` | `qdrant.NewClient(&Config{})` |
| **Java** | `io.qdrant:client` | `QdrantClient.newBuilder(url).build()` |
| **.NET** | `Qdrant.Client` | `new QdrantClient(url, apiKey)` |

### Core Operations

| Operation | MCP Query | Reference |
|-----------|-----------|-----------|
| Create collection | `"create collection vectors"` | `references/concepts.md` |
| Insert vectors | `"upsert points batch"` | `references/examples.md` |
| Search | `"search vectors similarity"` | `references/examples.md` |
| Filter | `"payload filter must match"` | `references/concepts.md` |
| Hybrid search | `"hybrid search sparse dense"` | `references/concepts.md` |

### Distance Metrics

- **Cosine**: Normalized similarity (default for text embeddings)
- **Euclid**: L2 distance (good for image embeddings)
- **Dot**: Inner product (when vectors are pre-normalized)
- **Manhattan**: L1 distance (sparse data, outlier-resistant)

## Best Practices

### Performance
1. **Batch operations**: Upsert in batches of 100-500 points
2. **Payload indexes**: Create indexes on frequently filtered fields
3. **Quantization**: Use scalar/binary quantization for large collections
4. **Sharding**: Consider for collections over 1M vectors
5. **gRPC**: Use gRPC client for high-throughput scenarios

### Security
1. **API Keys**: Always use environment variables, never hardcode
2. **Read-only keys**: Use for search-only applications
3. **Network**: Use private endpoints in production

### Architecture
1. **Collection per use case**: Don't mix different embedding types
2. **Named vectors**: Use when storing multiple vector types per point
3. **Payload structure**: Keep payloads flat for better filtering performance

## Using MCP Effectively

### When to Use lookup-snippet

**Always use MCP for:**
- Client-specific syntax (APIs change between versions)
- Complex operations (hybrid search, multi-vector)
- New features you haven't used before
- Language-specific patterns

**Example queries:**
```
"qdrant python create collection"
"javascript upsert points payload"
"rust search with filter"
"hybrid search bm25 dense"
```

### When to Use Reference Docs

**Use skill references for:**
- Conceptual understanding (what is quantization?)
- Architecture decisions (when to shard?)
- Cloud setup and configuration
- Best practices and patterns

## Resources

### references/
Contains detailed documentation loaded on demand:
- `clients.md`: Client library specifics for each language
- `cloud.md`: Qdrant Cloud setup, clusters, API keys
- `concepts.md`: Collections, vectors, filtering, quantization
- `examples.md`: Common code patterns and recipes

Load these references when detailed information is needed beyond what MCP provides.

### External Resources
- Qdrant Documentation: https://qdrant.tech/documentation/
- Qdrant Cloud Console: https://cloud.qdrant.io/
- GitHub: https://github.com/qdrant/qdrant
