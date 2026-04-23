# Cortex - Memory for Claude Code

Persistent memory across sessions. Remember what worked, recall when needed.

## Tools (5 total)

| Tool | Signature | Purpose |
|------|-----------|---------|
| `remember` | `remember(kind, text, tags?, ttl_days?)` | Store a memory |
| `recall` | `recall(query, kinds?, tags?, since_days?, limit?)` | Search memories |
| `list_recent` | `list_recent(kind?, limit?)` | Recent memories |
| `delete` | `delete(memory_id)` | Remove a memory |
| `doctor` | `doctor()` | Diagnostics |

## Memory Kinds

- **episode** - What happened (errors, solutions, commands)
- **fact** - Stable knowledge (conventions, constraints)
- **recipe** - How-to instructions (build, deploy, test)

## Memory Contract

**Before implementing:**
```python
recall(query="<task description>")
```

**After completing:**
```python
# Store what you learned
remember(kind="episode", text="Fixed X by doing Y")
remember(kind="fact", text="Project uses X convention")
remember(kind="recipe", text="To deploy: run X, then Y")
```

## Recall Ranking

Results are ranked by:
1. **Semantic similarity** to query
2. **Freshness** - newer memories score higher
3. **Verified boost** - verified memories score higher
4. **Query-type fit**:
   - "fix", "bug", "error" queries prefer episodes
   - "how", "run", "deploy" queries prefer recipes
   - "what", "convention" queries prefer facts

## Filtering

```python
# By kind
recall(query="auth", kinds=["episode", "fact"])

# By tags
recall(query="deployment", tags=["production"])

# By recency
recall(query="recent bugs", since_days=7)
```

## TTL Defaults

| Kind | Default TTL |
|------|-------------|
| episode | 90 days |
| fact | 365 days |
| recipe | 180 days |

Override with `ttl_days` parameter:
```python
remember(kind="episode", text="...", ttl_days=30)
```

## Troubleshooting

Run `doctor()` to check:
- Qdrant connection
- Embedder status
- Repo detection

## Architecture

```
server.py              # MCP tools (thin shim)
harness/
  router.py            # Routes to skills
  context.py           # Builds SkillContext
  policy.py            # Security enforcement
skills/
  remember/skill.py    # Store memories
  recall/skill.py      # Search with ranking
  recent/skill.py      # List by time
  delete/skill.py      # Remove memories
  store/
    qdrant_store.py    # Qdrant operations
    embedder.py        # Text embeddings
    schema.py          # MemoryRecord
```
