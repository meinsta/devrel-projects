# Codex + Qdrant: Persistent Engineering Memory

This repo packages one concrete Codex use case: give Codex a Qdrant-backed memory layer so it can retrieve architecture decisions, incident notes, and release runbooks before it edits code.

The workflow is cloud-first:

1. Use `qcloud` to identify a Qdrant Cloud cluster and create a cluster API key.
2. Seed a small memory corpus into that cloud cluster.
3. Register the official Qdrant MCP server with Codex against the cluster endpoint.
4. Ask Codex to query memory first, then plan or implement with that context.
5. Store any newly learned invariant back into Qdrant for later sessions.

Why this use case fits the official docs:

- Codex supports MCP servers for external tools and context: [OpenAI Codex docs](https://developers.openai.com/codex/mcp)
- Codex works better when you provide concrete context and verification steps: [OpenAI Codex prompting](https://developers.openai.com/codex/prompting), [OpenAI Codex workflows](https://developers.openai.com/codex/workflows)
- Qdrant has an official MCP server with `qdrant-store` and `qdrant-find`: [qdrant/mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant)
- Qdrant Cloud has an official management CLI for clusters and keys: [qdrant/qcloud-cli](https://github.com/qdrant/qcloud-cli)
- Qdrant's Python client supports FastEmbed-backed uploads to a remote cluster: [qdrant/qdrant-client](https://github.com/qdrant/qdrant-client), [Qdrant OpenAI page](https://qdrant.tech/documentation/embeddings/openai/)

## Quickstart

If you already have a cluster endpoint and cluster API key, skip to step 3.

If you only have a `qcloud` management context:

```bash
qcloud context set my-cloud --api-key <QDRANT_CLOUD_MANAGEMENT_KEY> --account-id <ACCOUNT_ID>
qcloud cluster list
export QDRANT_CLUSTER_ID=<cluster-id>
eval "$(python3 scripts/bootstrap_qdrant_cloud_env.py)"
```

That prints and exports `QDRANT_URL` and `QDRANT_API_KEY` for the cluster data plane.

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Seed the sample engineering memory:

```bash
python scripts/seed_memory.py
```

Preview retrieval against the cloud cluster before wiring Codex:

```bash
python scripts/query_memory.py "How do we handle tenant filters in search?"
```

Register the Qdrant MCP server with Codex:

```bash
./scripts/register_qdrant_mcp.sh
```

Then start Codex in this repo and use a prompt like:

```text
Before proposing any code changes, use qdrant-find to retrieve prior notes about tenant filters,
ranking regressions, and release checks. Summarize the constraints, propose the safest patch,
and list the exact validation steps you would run.
```

After a task, you can ask Codex to persist new knowledge:

```text
Use qdrant-store to save the root cause we just found, plus the regression test command,
under collection codex-memory.
```

## qcloud vs runtime

- `qcloud` is the management plane. Use it to select clusters, inspect endpoints, and create cluster API keys.
- Codex, the MCP server, and the Python client talk to the cluster endpoint in `QDRANT_URL`.
- Based on the current `andre/skills` conventions, this pattern fits better as a companion command or starter template than as a plain passive leaf skill. Let the scripts handle `qcloud` and Codex MCP registration.

## Files

- `use-cases/qdrant-codex-memory.md` explains the use case and prompt patterns.
- `memory/` contains sample ADRs, incident notes, and runbooks to seed.
- `scripts/bootstrap_qdrant_cloud_env.py` turns a `qcloud` cluster ID into `QDRANT_URL` and `QDRANT_API_KEY` exports.
- `scripts/seed_memory.py` chunks and uploads the memory corpus into Qdrant Cloud.
- `scripts/query_memory.py` tests retrieval against the target cluster without needing Codex.
- `scripts/register_qdrant_mcp.sh` registers the official Qdrant MCP server with Codex.
