# CAGE test strategy

## the cage test

the fundamental question: does an agent produce better code inside the cage
than outside it?

### method

1. build a realistic fullstack project (FastAPI + Next.js, 2 services, shared contracts)
2. give 5 tasks to an uncaged agent, record violations
3. give the same 5 tasks to a caged agent, record violations
4. CAGE passes if the caged agent produces zero violations on tasks the uncaged agent fails

### the 5 tasks

1. "add a new event type" (tests: contract enforcement)
2. "add a new API endpoint and consume it in frontend" (tests: import centralization)
3. "copy user validation from auth into billing" (tests: boundary enforcement + vector detection)
4. "rename 'status' to 'state' across the app" (tests: API snapshot validation)
5. "run the backend on port 3000" (tests: policy enforcement)

### metrics

| metric | uncaged | caged | pass condition |
|--------|---------|-------|----------------|
| contract violations | ? | 0 | caged = 0 |
| boundary crossings | ? | 0 | caged = 0 |
| hardcoded values | ? | 0 | caged = 0 |
| import bypasses | ? | 0 | caged = 0 |
| blocked commands | N/A | >0 | cage blocked at least 1 |
| pre-commit catches | N/A | >0 | checks caught violations |
| pipeline gating | N/A | yes | /feature refused without spec |

## smoke tests (automated)

### 01-contract-violation
project with hardcoded "active" instead of shared/domain-values.json STATUS_ACTIVE.
PASS: cage check catches it.

### 02-boundary-crossing
services/billing/handler.ts imports from services/auth/internal/hash.ts.
PASS: cage check catches it.

### 03-import-bypass
handler uses raw fetch() instead of lib/api-client.ts.
PASS: cage check catches it.

### 04-api-snapshot-drift
API handler returns { state: "active" } but snapshot says { status: "active" }.
PASS: cage check catches it.

### 05-policy-enforcement
simulate agent running "kill 1234".
PASS: check-policy hook blocks it, suggests "cage infra stop".

### 06-pipeline-gating
try /cage-feature without approved spec.
PASS: pipeline rejects with "run /cage-spec first".

### 07-merge-safety
cage merge on branch with conflicts.
PASS: refuses, lists conflicting files.

### 08-cage-search
index project, search "authentication".
PASS: returns relevant auth files ranked by similarity.

### 09-hybrid-detection (the killer test)
project where service B reimplemented (not imported) logic from service A.
no import to flag. pure LSP/AST misses it.
PASS: vector layer detects semantic similarity, flags as potential violation.
this test proves the hybrid architecture matters.

### 10-cage-doctor
project with missing hooks, stale index, no contracts.
PASS: doctor reports all 3 issues.

## test infrastructure

- unit tests: bun test for cage-core internals
- integration tests: pre-built fixtures in test/fixtures/
- smoke tests: shell scripts in test/smoke/ that run cage commands against fixture projects
- the cage test: manual comparison, run before each release
