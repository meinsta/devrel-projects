# Use Case: Qdrant-Backed Memory For Codex

## Problem

Codex is strongest when it has the right context and clear verification steps, but that context is often scattered across ADRs, runbooks, and postmortems. Engineers end up re-explaining the same constraints every time they open a new Codex thread.

## Solution

Store durable engineering knowledge in Qdrant Cloud and let Codex access it through the official Qdrant MCP server. In practice, that gives Codex a searchable memory layer it can consult before changing code.

Treat `qcloud` as the management plane, not the runtime query path. Use it to discover cluster endpoints and create cluster API keys, then point Codex and the Qdrant client at the cluster URL directly.

## Good Fit

Use this when your team has:

- multi-tenant invariants that must not be broken
- recurring incident patterns that should influence future fixes
- runbooks or release checks that Codex should follow before it reports success
- long-lived projects where important context outlasts any single chat thread

## Workflow

1. Use `qcloud` to select a cluster and create a cluster API key.
2. Seed ADRs, incidents, and runbooks into the Qdrant Cloud collection.
3. Register Qdrant as an MCP server for Codex.
4. Prompt Codex to start with `qdrant-find` before it plans or edits.
5. After a task, prompt Codex to save any durable lesson with `qdrant-store`.

## Example Prompts

Use these directly in Codex once the MCP server is registered:

```text
Use qdrant-find to pull prior decisions about tenant filters and ranking regressions.
Summarize the constraints that any search change must preserve, then propose a minimal patch plan.
```

```text
Search Qdrant memory for release checks related to search changes.
After you summarize them, implement the fix and re-run the exact checks you found.
```

```text
After you finish, store the new invariant we learned with qdrant-store.
Include metadata for source="codex-session" and topic="search-safety".
```

## Why This Matches The Docs

- OpenAI's Codex docs describe MCP as the way to give Codex access to external tools and context.
- OpenAI's prompting and workflows docs recommend giving Codex concrete context plus explicit verification steps.
- Qdrant's official MCP server is explicitly positioned as a semantic memory layer.
- `qcloud` is the natural management tool when you already operate on Qdrant Cloud and plan to package this pattern for reuse.

## Packaging Note

The current `andre/skills` repo is optimized for passive Qdrant guidance: short SKILL files, mostly read-only behavior, and links that stay inside Qdrant documentation. That makes this Codex + `qcloud` + MCP workflow a better fit for a companion command, starter template, or separate integration example than for a plain leaf skill.

If you still move part of this into a Qdrant skill release, keep the skill passive and portable. The skill should explain when to use cloud-backed memory and when to query it first; the mutable steps such as `qcloud` bootstrap, cluster key creation, and Codex MCP registration belong in scripts.
