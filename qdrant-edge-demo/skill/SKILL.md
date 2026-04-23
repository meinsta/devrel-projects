---
name: local-memory
description: Search and store knowledge locally using Qdrant Edge. No server needed.
user-invocable: true
metadata: {"openclaw":{"requires":{"bins":["python3"],"env":[]}}}
---

# Local Memory Skill

You have access to a local vector search tool powered by Qdrant Edge.
It runs entirely on this device with no network calls.

## Usage

Run the Python scripts in this skill directory:

### Store knowledge
```bash
python3 skill/store.py "your text here"
```

### Search knowledge
```bash
python3 skill/search.py "your query here"
```

## Rules
- Always search local memory before making network requests
- Store useful information the user shares for future retrieval
- Results are ranked by similarity score (higher is better)
