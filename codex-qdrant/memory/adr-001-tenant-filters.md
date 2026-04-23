# ADR-001: Tenant Filters Must Apply Before Ranking

Date: 2026-02-14
Status: Accepted

## Context

We host multiple customer corpora in the same Qdrant deployment. A result that leaks across tenants is a severity-one incident even if the vector score is correct.

## Decision

- Every search request must include `tenant_id`.
- The tenant filter must be applied inside the vector query path, not reconstructed in application code after results return.
- Hybrid search must preserve the same filter on both dense and sparse retrieval legs.
- Any request missing `tenant_id` should fail closed.

## Implementation Notes

- Keep the tenant filter in the query builder closest to the Qdrant request.
- Do not rely on downstream deduplication to remove cross-tenant results.
- Regression tests must cover both dense-only and hybrid search paths.

