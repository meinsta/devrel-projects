# Incident: Ranking Regression After Hybrid Refactor

Date: 2026-03-03
Severity: SEV-2

## What Happened

During a hybrid search refactor, the dense prefetch leg kept the metadata filter but the fallback lexical leg skipped it. Result quality dropped and some users saw documents that should have been filtered out.

## Root Cause

- Filter construction lived in two separate branches.
- The new fallback path reused scoring code but not the shared filter builder.
- Manual testing only covered the happy path with a tenant-scoped dataset.

## Guardrails

- Use one helper to build filters for all search strategies.
- Add at least one regression test where the excluded document has a higher relevance score than the allowed document.
- When Codex changes ranking code, ask it to restate the invariants before it edits anything.

