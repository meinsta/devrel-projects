# Runbook: Required Checks For Search Changes

Owner: Search Platform

## Required Validation

- Run the smallest relevant automated test suite for dense and hybrid retrieval.
- Run one manual query that is known to require `tenant_id` filtering.
- Compare before and after results for at least one query with a restrictive metadata filter.
- Verify that logging still records strategy name, limit, and filter summary.

## Release Notes

- If search ranking logic changes, document whether score distribution shifted.
- If filter logic changes, call out user-visible safety impact in the change summary.
- If Codex performed the task, ask it to report the exact commands it ran and their results.

